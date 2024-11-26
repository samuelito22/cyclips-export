import subprocess
import json
from decimal import Decimal
from typing import Tuple
import tempfile
import base64
import re
import os

def fetch_video_metadata(video_path: str):
    """
    Fetches video metadata using ffprobe.

    Args:
        video_path (str): Path to the video file.

    Returns:
        dict: Dictionary containing video metadata.
    """
    command = [
        "ffprobe",
        "-v", "error",              
        "-print_format", "json",  
        "-show_format",            
        "-show_streams",           
        video_path
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        text=True
    )

    if result.returncode == 0:
        try:
            metadata = json.loads(result.stdout)
            return metadata
        except json.JSONDecodeError:
            raise ValueError("Failed to decode metadata output as JSON.")
    else:
        raise RuntimeError(f"Error fetching metadata: {result.stderr}")

def trim_video(
    video_path: str, 
    output_path: str, 
    start: Decimal, 
    end: Decimal,
    fps: Decimal,
    no_audio: bool = False  
):
    """
    Trims a video file to the specified start and end times.

    Args:
        video_path (str): Path to the input video.
        output_path (str): Path to save the trimmed video.
        start (Decimal): Start time in seconds as a Decimal.
        end (Decimal): End time in seconds as a Decimal.
        no_audio (bool): Whether to remove audio from the trimmed video.
    """
    duration = end - start
    if duration <= 0:
        raise ValueError("End time must be greater than start time.")

    frame_duration = Decimal(1/fps)
    if duration <= frame_duration:
        command = [
            "ffmpeg",
            "-y",  
            "-ss", f"{start:.6f}",
            "-i", video_path, 
            "-vf", f"select='eq(n,0)',setpts=PTS-STARTPTS",  
            "-frames:v", "1",
            "-c:v", "libx264", 
            "-crf", "18",
            "-an"
        ]
    else:
        command = [
            "ffmpeg",
            "-y", 
            "-ss", f"{start:.6f}",
            "-i", video_path,
            "-t", f"{duration:.6f}",
            "-c:v", "libx264",  
            "-crf", "18",  
        ]
    
    if no_audio:
        command.extend(["-an"])
        
    command.extend([output_path])

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,  
            text=True  
        )
        if result.returncode == 0:
            print(f"Video trimmed and saved to {output_path}")
        else:
            print(f"Error trimming video: {result.stderr}")
    except subprocess.CalledProcessError as e:
        print(f"Error trimming video: {e.stderr}")
        
def extract_audio(
    video_path: str, 
    output_path: str, 
):
    """
    Extracts audio from a video file and saves it to the specified output file.

    Args:
        video_path (str): Path to the input video.
        output_path (str): Path to save the extracted audio.
    """
    command = [
        "ffmpeg",
        "-y", 
        "-i", video_path,
        "-vn", 
        output_path
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,  
            text=True  
        )
        if result.returncode == 0:
            print(f"Audio extracted and saved to {output_path}")
        else:
            print(f"Error extracting audio: {result.stderr}")
    except subprocess.CalledProcessError as e:
        print(f"Error extracting audio: {e.stderr}")

def apply_fit(input_path: str, output_path: str, video_width: float, video_height: float, aspect_ratio: Tuple[str, str]):
    """
    Create a background frosted glass effect with blurred edges for a video segment.
    """
    aspect_ratio_width, aspect_ratio_height = aspect_ratio
    if video_width / video_height > aspect_ratio_width / aspect_ratio_height:
        output_width = video_height * (aspect_ratio_width / aspect_ratio_height)
        output_height = video_height
    else:
        output_width = video_width
        output_height = video_width * (aspect_ratio_height / aspect_ratio_width)

    output_width = round(output_width / 2) * 2
    output_height = round(output_height / 2) * 2

    command = [
        'nice', 'ffmpeg', '-y', '-i', input_path, '-i', input_path,
        '-filter_complex', (
            f"[0:v]scale={video_width}:{video_height},gblur=sigma=10,crop={output_width}:{output_height},"
            f"setsar=1/1[b];"
            f"[1:v]scale={output_width}:-2,setsar=1[f];"
            f"[b][f]overlay=(W-w)/2:(H-h)/2:enable=1,format=rgba,colorchannelmixer=aa=0.9"
        ),
        '-c:v', 'libx264', '-crf', '17', '-an', output_path
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,  
            text=True  
        )
        if result.returncode == 0:
            print(f"Successfully applyed fit layout and saved to {output_path}")
        else:
            print(f"Error applying fit layout: {result.stderr}")
    except subprocess.CalledProcessError as e:
        print(f"Error applying fit layout: {e.stderr}")
            
def apply_fill(scene: dict, input_path:str, output_path:str, video_width: float, video_height: float):
    """
    Apply a bounding box effect to a video segment using crop_width and crop_height from the scene.
    """
    
    top_left_x, top_left_y = scene['top_left']
    
    top_left_x = top_left_x * video_width
    top_left_y = top_left_y * video_height

    crop_width = scene['crop_width'] * video_width
    crop_height = scene['crop_height'] * video_height
    
    output_width = round(crop_width / 2) * 2
    output_height = round(crop_height / 2) * 2

    command = [
        'nice', 'ffmpeg', '-y', '-ss', '0', '-i', input_path,
        '-vf', f"scale=w={video_width}:h={video_height},setsar=1/1,crop=w={output_width}:h={output_height}:x={top_left_x}:y={top_left_y}",
        '-c:v', 'libx264', '-crf', '17',
        output_path
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,  
            text=True  
        )
        if result.returncode == 0:
            print(f"Successfully applyed fill layout and saved to {output_path}")
        else:
            print(f"Error applying fill layout: {result.stderr}")
    except subprocess.CalledProcessError as e:
        print(f"Error applying fill layout: {e.stderr}")
        
def attach_audio(video_path: str, audio_path: str, output_path: str):
    """
    Attaches an audio track to a video file and saves it to the specified output file.

    Args:
        video_path (str): Path to the input video.
        audio_path (str): Path to the input audio file.
        output_path (str): Path to save the output video with attached audio.
    """
    command = [
        "ffmpeg",
        "-y",  
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",  
        "-c:a", "copy",  
        "-shortest", 
        output_path
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True
        )
        if result.returncode == 0:
            print(f"Audio attached successfully and saved to {output_path}")
        else:
            print(f"Error attaching audio: {result.stderr}")
    except subprocess.CalledProcessError as e:
        print(f"Error attaching audio: {e.stderr}")
        
def attach_subtitles(input_path: str, subtitles_path: str, output_path: str):
    """
    Extract the Base64 font data from the .ass file, decode it, save it as a temporary file,
    and use it to attach subtitles and the extracted font to the video using FFmpeg.
    """
    try:
        with open(subtitles_path, "r") as file:
            subtitle_content = file.read()
        
        font_match = re.search(r"data: (.+)", subtitle_content)
        if not font_match:
            raise ValueError("No Base64 font data found in the subtitles file.")
        
        base64_font_data = font_match.group(1)
        
        with tempfile.NamedTemporaryFile(suffix=".ttf") as temp_font_file:
            temp_font_file.write(base64.b64decode(base64_font_data))
            temp_font_file.flush()  
            
            font_path = temp_font_file.name  

            command = [
                "ffmpeg", "-y", "-i", input_path,
                "-vf", f"subtitles={subtitles_path}:fontsdir={os.path.dirname(font_path)}",
                "-c:v", "libx264",
                "-crf", "18",
                output_path
            ]

            
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True
            )
            
            if result.returncode == 0:
                print(f"Subtitles and font attached successfully. Output saved to {output_path}")
            else:
                print(f"Error attaching subtitles: {result.stderr}")
    
    except subprocess.CalledProcessError as e:
        print(f"Error attaching subtitles: {e.stderr}")
    except ValueError as e:
        print(f"Error processing font data: {str(e)}")
        
        