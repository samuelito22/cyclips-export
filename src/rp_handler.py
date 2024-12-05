"""
rp_handler.py for RunPod Worker

rp_debugger:
- Utility that provides additional debugging information.
- The handler must be called with --rp_debugger flag to enable it.
"""

import base64
import tempfile
import os
from typing import Optional

from dotenv import load_dotenv
from runpod.serverless.utils import download_files_from_urls, rp_debugger, rp_cleanup
from runpod.serverless.utils.rp_validator import validate
import runpod

from rp_schema import INPUT_VALIDATIONS
from export import Exporter
from utils.azure import upload_file

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
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as temp_file:
        temp_file.write(base64.b64decode(base64_file))
    return temp_file.name

@rp_debugger.FunctionTimer
def handler(job: dict):
    try:
        rp_debugger.clear_debugger_output()

        with rp_debugger.LineTimer('validation_step'):
            input_validation = validate(job.get('input', {}), INPUT_VALIDATIONS)
            if 'errors' in input_validation:
                return {"error": input_validation['errors']}
            job['input'] = input_validation['validated_input']

        task = job['input'].get('task')
        if task == 'export-clips':
            job_input = job['input']  

            def progress_callback(progress, message):
                status_data = {
                    "progress": progress,
                    "message": message,
                }
                runpod.serverless.progress_update(job, status_data)

            subtitles_path = base64_to_tempfile(job_input["subtitles"]) if job_input["subtitles"] else None

            with rp_debugger.LineTimer(f"download_step"):
                scenes_path = download_files_from_urls(job["id"], [job_input["scenes_url"]])[0]

            with rp_debugger.LineTimer(f"export_step"):
                with tempfile.NamedTemporaryFile(suffix=".mp4") as temp_file:
                    Exporter(progress_callback=progress_callback).export(
                        video_url=job_input["video_url"],
                        start=job_input["start"],
                        end=job_input["end"],
                        scenes_path=scenes_path,
                        subtitles_path=subtitles_path,
                        output_path=temp_file.name
                    )

                    upload_file(job_input["destination_url"], temp_file.name)

            return {"status": "completed"}

        return {"error": f"Unsupported task type: {task}"}

    except Exception as e:
        print(e)
            
        return {"error": f"An error occurred: {str(e)}"}
    finally:
        with rp_debugger.LineTimer(f"cleanup_step"):
            rp_cleanup.clean(["tmp"])

runpod.serverless.start({"handler": handler})
