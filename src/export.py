import subprocess
import tempfile
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from utils.video import *
from typing import Tuple
import shutil

class Exporter:
    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback
    
    def _update_progress(self, progress, message):
        if self.progress_callback:
            self.progress_callback(progress, message)
            
    def export(
        self, 
        video_path: str,
        start: float,
        end: float,
        scenes_path: str,
        output_path: str,
        aspect_ratio: Tuple[str, str] = (9, 16),
        subtitles_path: str = None
    ):
        start = Decimal(str(start))
        end = Decimal(str(end))
        duration = end - start

        with tempfile.TemporaryDirectory() as temp_dir:
            metadata = fetch_video_metadata(video_path)
            video_width = int(metadata["streams"][0]["width"])
            video_height = int(metadata["streams"][0]["height"])
            video_fps = Decimal(eval(metadata["streams"][0]["avg_frame_rate"]))
            min_frame_duration = Decimal(1) / video_fps
            
            trimmed_clip_path = f"{temp_dir}/trimmed_clip.mp4"
            intermediate_clip_path = f"{temp_dir}/intermediate_clip.mp4"
            final_trimmed_path = f"{temp_dir}/final_trimmed_clip.mp4"
            
            # Trim the video
            self._update_progress(10, "Trimming the video...")
            trim_video(
                video_path=video_path, 
                output_path=trimmed_clip_path, 
                start=start, 
                end=end, 
                fps=video_fps
            )

            # Extract audio if needed
            audio_path = f"{temp_dir}/audio.aac" if duration > min_frame_duration else None
            if audio_path:
                self._update_progress(20, "Extracting audio...")
                extract_audio(trimmed_clip_path, audio_path)
                            
            # Process scenes
            self._update_progress(30, "Processing scenes...")
            scenes = self._get_scenes(start, end, scenes_path, reset=False)
            scene_paths = [f"{temp_dir}/scene_{i}.mp4" for i, _ in enumerate(scenes)]
            with ThreadPoolExecutor() as executor:
                executor.map(
                    self._create_scene,
                    scenes,
                    [video_path] * len(scenes), 
                    [video_width] * len(scenes), 
                    [video_height] * len(scenes), 
                    [video_fps] * len(scenes), 
                    [aspect_ratio] * len(scenes), 
                    scene_paths 
                )

            # Concatenate scenes
            self._update_progress(50, "Concatenating scenes...")
            concat_file_path = f"{temp_dir}/concat_list.txt"
            with open(concat_file_path, 'w') as concat_file:
                for scene_path in scene_paths:
                    concat_file.write(f"file '{scene_path}'\n")

            concatenated_clip_path = f"{temp_dir}/concatenated_clip.mp4"
            self._concatenate_videos(concatenated_clip_path, concat_file_path, audio_path=None)

            # Final trim after concatenation
            self._update_progress(70, "Final trimming and attaching audio...")
            trim_video(
                video_path=concatenated_clip_path, 
                output_path=intermediate_clip_path, 
                start=max(start - scenes[0]["start_time"], 0), 
                end=end, 
                fps=video_fps
            )

            # Attach audio
            attach_audio(
                video_path=intermediate_clip_path,
                audio_path=audio_path,
                output_path=final_trimmed_path
            )
            
            if subtitles_path: 
                self._update_progress(90, "Attaching subtitles...")
                attach_subtitles(final_trimmed_path, subtitles_path, output_path)
            else:
                shutil.copy(final_trimmed_path, output_path)
                
        self._update_progress(100, "Export completed successfully!")

    def _create_scene(
        self,
        scene: dict,
        video_path: str,
        video_width: int,
        video_height: int,
        video_fps: Decimal,
        aspect_ratio: Tuple[str, str],
        output_path: str
    ):
        scene_start = scene["start_time"]
        scene_end = scene["end_time"]

        with tempfile.TemporaryDirectory() as temp_dir:
            segment_path = f"{temp_dir}/segment.mp4"
            trim_video(
                video_path=video_path, 
                output_path=segment_path, 
                start=scene_start, 
                end=scene_end, 
                fps=video_fps,
                no_audio=True
            )

            if scene["type"] == "fill":
                apply_fill(
                    scene=scene, 
                    input_path=segment_path, 
                    output_path=output_path,
                    video_height=video_height,
                    video_width=video_width,
                    )
            elif scene["type"] == "fit":
                
                apply_fit(
                    input_path=segment_path, 
                    output_path=output_path,
                    video_height=video_height,
                    video_width=video_width,
                    aspect_ratio=aspect_ratio
                    )
            else:
                raise ValueError(f"Unknown scene type: {scene['type']}")

    def _concatenate_videos(self, output_path:str, concat_file_path:str, audio_path: str = None):
        command = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file_path,
        ]

        if audio_path:
            command.extend(["-i", audio_path])

        command.extend([
            "-shortest",
            "-c:v", "libx264",
            "-crf", "17",
            output_path,
        ])
        
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,  
                text=True  
            )
            if result.returncode == 0:
                print(f"Successfully concatenated segments")
            else:
                print(f"Error concatenating segments: {result.stderr}")
        except subprocess.CalledProcessError as e:
            print(f"Error concatenating segments: {e.stderr}")
            

    def _get_scenes(self, start: Decimal, end: Decimal, scenes_path: str, reset: bool = True):
        with open(scenes_path, "r") as file:
            all_scenes = json.load(file)

        filtered_boxes = [
            scene for scene in all_scenes
            if not (scene["end_time"] < start or scene["start_time"] > end) 
        ]
        filtered_boxes = [ 
            {
                **scene, 
                "start_time": Decimal(str(scene["start_time"])), 
                "end_time": Decimal(str(scene["end_time"]))
            } for scene in filtered_boxes ]

        if reset and filtered_boxes:
            time_offset = start

            for box in filtered_boxes:
                box["start_time"] = max(box["start_time"] - time_offset, Decimal(0))
                box["end_time"] = max(box["end_time"] - time_offset, Decimal(0))

            filtered_boxes[0]["start_time"] = Decimal(0)
            filtered_boxes[-1]["end_time"] = end - start

        return filtered_boxes
