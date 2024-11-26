from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
load_dotenv()

import runpod
import base64
import tempfile

from rp_schema import INPUT_VALIDATIONS
from runpod.serverless.utils import download_files_from_urls, rp_cleanup, rp_debugger
from runpod.serverless.utils.rp_validator import validate
from export import Exporter
from utils.azure import upload_file

def is_valid_base64(data):
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
    '''
    Convert base64 file to tempfile.

    Parameters:
    base64_file (str): Base64 file

    Returns:
    str: Path to tempfile
    '''
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_file.write(base64.b64decode(base64_file))

    return temp_file.name

def process_export(job_id, video_url, start, end, scenes_url, subtitles, destination_url):
    """Process a single export task."""
    subtitles_path = None
    if subtitles:
        subtitles_path = base64_to_tempfile(subtitles)
    
    # Download scenes file
    with rp_debugger.LineTimer('download_step'):
        scenes_path = download_files_from_urls(job_id, [scenes_url])[0]
    
    # Export video
    with rp_debugger.LineTimer('export_step'):
        with tempfile.NamedTemporaryFile(suffix=".mp4") as temp_file:
            temp_path = temp_file.name
            
            Exporter().export(
                video_path=video_url,
                start=start,
                end=end,
                scenes_path=scenes_path,
                subtitles_path=subtitles_path,
                output_path=temp_path
            )
            
            # Upload the exported video
            upload_file(destination_url, temp_path)

def handler(job):
    """Handler function to process jobs."""
    job_input = job.get('input', {})

    with rp_debugger.LineTimer('validation_step'):
        input_validation = validate(job_input, INPUT_VALIDATIONS)

        if 'errors' in input_validation:
            return {"error": input_validation.get('errors')}
        
        job_input = input_validation.get('validated_input', {})

    task = job_input.get('task')

    if task == 'export':
        # Validate inputs for a single export
        if not job_input.get('video_url'):
            return {"error": "Missing required field: video_url"}
        if not job_input.get('destination_url'):
            return {"error": "Missing required field: destination_url"}
        
        if job_input.get('start', 0) >= job_input.get('end', 0):
            return {"error": f"Invalid time range."}

        if job_input.get('subtitles') and not is_valid_base64(job_input.get('subtitles')):
            return {"error": "Invalid base64 encoding for subtitles"}

        # Process single export
        process_export(
            job_id=job['id'],
            video_url=job_input["video_url"],
            start=job_input["start"],
            end=job_input["end"],
            scenes_url=job_input["scenes_url"],
            subtitles=job_input.get("subtitles"),
            destination_url=job_input["destination_url"]
        )

    elif task == 'batch-export':
        # Validate inputs for batch export
        if not job_input.get('batch'):
            return {"error": "Missing required field: batch"}
        
        for entry in job_input.get('batch', []):
            if not entry.get('destination_url'):
                return {"error": "Each batch entry must have a destination_url"}
            if entry.get('start', 0) >= entry.get('end', 0):
                return {"error": f"Invalid time range in batch entry: {entry}"}
            if entry.get('subtitles') and not is_valid_base64(entry.get('subtitles')):
                return {"error": f"Invalid base64 encoding for subtitles in batch entry: {entry}"}

        # Process batch in parallel
        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(
                    process_export,
                    job_id=job['id'],
                    video_url=entry["video_url"],
                    start=entry["start"],
                    end=entry["end"],
                    scenes_url=entry["scenes_url"],
                    subtitles=entry.get("subtitles"),
                    destination_url=entry["destination_url"]
                )
                for entry in job_input.get('batch', [])
            ]
            
            # Wait for all tasks to complete
            for future in futures:
                future.result()

    else:
        return {"error": f"Unsupported task type: {task}"}
    
    with rp_debugger.LineTimer('cleanup_step'):
        rp_cleanup.clean(['input_objects'])
    
    return {"status": "completed"}


# Start the serverless handler
runpod.serverless.start({"handler": handler})
