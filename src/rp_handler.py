"""
rp_handler.py for RunPod Worker

rp_debugger:
- Utility that provides additional debugging information.
- The handler must be called with --rp_debugger flag to enable it.
"""

import base64
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from dotenv import load_dotenv
from runpod.serverless.utils import download_files_from_urls, rp_debugger, rp_cleanup
from runpod.serverless.utils.rp_validator import validate
import runpod

from rp_schema import INPUT_VALIDATIONS
from export import Exporter
from utils.azure import upload_file

# Load environment variables
load_dotenv()


def is_valid_base64(data: Optional[str]) -> bool:
    """
    Check if a string is valid base64.
    """
    if not data:
        return True
    try:
        base64.b64decode(data, validate=True)
        return True
    except Exception:
        return False


def base64_to_tempfile(base64_file: str) -> str:
    """
    Convert base64-encoded string to a temporary file.

    Parameters:
        base64_file (str): Base64-encoded string.

    Returns:
        str: Path to the created temporary file.
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_file.write(base64.b64decode(base64_file))
    return temp_file.name
    
def process_export(job: dict, video_url: str, start: float, end: float, scenes_url: str, subtitles: Optional[str], destination_url: str):

    def progress_callback(progress, message):
        status_data = {
            "progress": progress,
            "message": message,
        }
        runpod.serverless.progress_update(job, status_data)
        
    subtitles_path = base64_to_tempfile(subtitles) if subtitles else None

    # Download scenes file
    with rp_debugger.LineTimer('download_step'):
        scenes_path = download_files_from_urls(job["id"], [scenes_url])[0]

    # Export video
    with rp_debugger.LineTimer('export_step'):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
            Exporter(progress_callback).export(
                video_path=video_url,
                start=start,
                end=end,
                scenes_path=scenes_path,
                subtitles_path=subtitles_path,
                output_path=temp_file.name
            )
            # Upload the exported video
            upload_file(destination_url, temp_file.name)


@rp_debugger.FunctionTimer
def handler(job: dict):
    # Validate input and reconstruct the job
    with rp_debugger.LineTimer('validation_step'):
        input_validation = validate(job.get('input', {}), INPUT_VALIDATIONS)
        if 'errors' in input_validation:
            return {"error": input_validation['errors']}
        job['input'] = input_validation['validated_input']

    task = job['input'].get('task')
    if task == 'export':
        return process_single_export(job)
    elif task == 'batch-export':
        return process_batch_export(job)
    return {"error": f"Unsupported task type: {task}"}


def process_single_export(job: dict):
    """
    Process a single export job.

    Parameters:
        job (dict): Job data.

    Returns:
        dict: Status of the export task.
    """
    job_input = job['input']  # Access the validated input directly

    # Validate required fields
    required_fields = ['video_url', 'destination_url']
    for field in required_fields:
        if not job_input.get(field):
            return {"error": f"Missing required field: {field}"}

    if job_input.get('start', 0) >= job_input.get('end', 0):
        return {"error": "Invalid time range."}

    if job_input.get('subtitles') and not is_valid_base64(job_input['subtitles']):
        return {"error": "Invalid base64 encoding for subtitles"}

    # Process export
    process_export(
        job=job,
        video_url=job_input["video_url"],
        start=job_input["start"],
        end=job_input["end"],
        scenes_url=job_input["scenes_url"],
        subtitles=job_input.get("subtitles"),
        destination_url=job_input["destination_url"]
    )
    
    with rp_debugger.LineTimer('cleanup_step'):
        rp_cleanup.clean(['input_objects'])
        
    return {"status": "completed"}



def process_batch_export(job: dict):
    """
    Process a batch export job.

    Parameters:
        job (dict): Job data.

    Returns:
        dict: Status of the batch export task.
    """
    job_input = job['input']  # Access the validated input directly

    # Validate batch field
    if not job_input.get('batch'):
        return {"error": "Missing required field: batch"}

    # Validate each batch entry
    for entry in job_input['batch']:
        if not entry.get('destination_url'):
            return {"error": f"Each batch entry must have a destination_url"}
        if entry.get('start', 0) >= entry.get('end', 0):
            return {"error": f"Invalid time range in batch entry: {entry}"}
        if entry.get('subtitles') and not is_valid_base64(entry['subtitles']):
            return {"error": f"Invalid base64 encoding for subtitles in batch entry: {entry}"}

    # Process batch in parallel
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                process_export,
                job=job,
                video_url=entry["video_url"],
                start=entry["start"],
                end=entry["end"],
                scenes_url=entry["scenes_url"],
                subtitles=entry.get("subtitles"),
                destination_url=entry["destination_url"]
            )
            for entry in job_input['batch']
        ]
        for future in futures:
            future.result()
            
    with rp_debugger.LineTimer('cleanup_step'):
        rp_cleanup.clean(['input_objects'])
        
    return {"status": "completed"}

# Start the serverless handler
runpod.serverless.start({"handler": handler})
