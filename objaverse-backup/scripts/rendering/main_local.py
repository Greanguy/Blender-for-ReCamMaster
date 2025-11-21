import glob
import json
import multiprocessing
import os
import platform
import random
import subprocess
import tempfile
import time
import zipfile
import gzip
import shutil
from functools import partial
from typing import Any, Dict, List, Literal, Optional, Union

import fire
import fsspec
import GPUtil
import pandas as pd
from loguru import logger

import sys
sys.path.append('..')
import objaverse.xl as oxl
from objaverse.utils import get_uid_from_str


def log_processed_object(csv_filename: str, *args) -> None:
    args = ",".join([str(arg) for arg in args])
    dirname = os.path.expanduser(f"~/.objaverse/logs/")
    os.makedirs(dirname, exist_ok=True)
    with open(os.path.join(dirname, csv_filename), "a", encoding="utf-8") as f:
        f.write(f"{time.time()},{args}\n")


def zipdir(path: str, ziph: zipfile.ZipFile) -> None:
    for root, dirs, files in os.walk(path):
        for file in files:
            arcname = os.path.join(os.path.basename(root), file)
            ziph.write(os.path.join(root, file), arcname=arcname)


def handle_found_object(
    local_path: str,
    file_identifier: str,
    sha256: str,
    metadata: Dict[str, Any],
    num_renders: int,
    render_dir: str,
    only_northern_hemisphere: bool,
    gpu_devices: Union[int, List[int]],
    render_timeout: int,
    successful_log_file: Optional[str] = "handle-found-object-successful.csv",
    failed_log_file: Optional[str] = "handle-found-object-failed.csv",
) -> bool:
    save_uid = get_uid_from_str(file_identifier)
    args = f"--object_path '{local_path}' --num_renders {num_renders}"

    using_gpu: bool = True
    gpu_i = 0
    if isinstance(gpu_devices, int) and gpu_devices > 0:
        num_gpus = gpu_devices
        gpu_i = random.randint(0, num_gpus - 1)
    elif isinstance(gpu_devices, list):
        gpu_i = random.choice(gpu_devices)
    elif isinstance(gpu_devices, int) and gpu_devices == 0:
        using_gpu = False
    else:
        raise ValueError(
            f"gpu_devices must be an int > 0, 0, or a list of ints. Got {gpu_devices}."
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        target_directory = os.path.join(temp_dir, save_uid)
        os.makedirs(target_directory, exist_ok=True)
        args += f" --output_dir {target_directory}"

        if platform.system() == "Linux" and using_gpu:
            args += " --engine BLENDER_EEVEE"
        elif platform.system() == "Darwin" or (
            platform.system() == "Linux" and not using_gpu
        ):
            args += " --engine CYCLES"
        else:
            raise NotImplementedError(f"Platform {platform.system()} is not supported.")

        if only_northern_hemisphere:
            args += " --only_northern_hemisphere"

        blender_path = os.path.join("/data1", "blender-3.2.2-linux-x64/blender")
        script_path = os.path.join(os.path.dirname(__file__), "blender_script.py")
        command = f"xvfb-run -a {blender_path} --background --python {script_path} -- {args}"
        if using_gpu:
            command = f"export DISPLAY=:0.{gpu_i} && {command}"

        logger.info(command)

        subprocess.run(
            ["bash", "-c", command],
            timeout=render_timeout,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        frames_dir = os.path.join(target_directory, "frames")
        videos_dir = os.path.join(target_directory, "videos")
        input_pattern = os.path.join(frames_dir, "%03d.png")

        cam_folders = []
        for item in os.listdir(target_directory):
            item_path = os.path.join(target_directory, item)
            if os.path.isdir(item_path) and item.startswith("cameras_cam"):
                # 提取camXX部分（例如从"cameras_cam01"提取"cam01"）
                cam_name_part = item.replace("cameras_", "")
                cam_folders.append(cam_name_part)
        existing_videos = []
        if os.path.exists(videos_dir):
            for video_file in os.listdir(videos_dir):
                if video_file.endswith(".mp4"):
                    # 去掉.mp4后缀得到camxx
                    cam_name_from_video = os.path.splitext(video_file)[0]
                    existing_videos.append(cam_name_from_video)
        cam_folders_set = set(cam_folders)
        existing_videos_set = set(existing_videos)
        missing_cams = cam_folders_set - existing_videos_set
        cam_name = sorted(list(missing_cams))[0]

        render_count = num_renders
        video_path = os.path.join(videos_dir, f"{cam_name}.mp4")
        # 使用ffmpeg将图片序列转换为视频
        # -framerate 30: 设置帧率为30fps
        # -i input_pattern: 输入图片序列
        # -c:v libx264: 使用H.264编码
        # -pix_fmt yuv420p: 设置像素格式以确保兼容性
        # -crf 23: 设置质量（0-51，数值越小质量越高）
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",  # 覆盖输出文件
            "-framerate", "30",  # 帧率
            "-start_number", "0",  # 起始帧编号
            "-i", input_pattern,  # 输入图片模式
            "-frames:v", str(render_count),  # 限制帧数
            "-c:v", "libx264",  # 视频编码器
            "-pix_fmt", "yuv420p",  # 像素格式
            "-crf", "23",  # 质量参数
            video_path
        ]
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)

        # cameras_dir = os.path.join(target_directory, "cameras")
        # png_files = glob.glob(os.path.join(frames_dir, "*.png"))
        # metadata_files = glob.glob(os.path.join(frames_dir, "*.json"))
        # npy_files = glob.glob(os.path.join(cameras_dir, "*.npy"))
        # if (
        #     (len(png_files) != num_renders)
        #     or (len(npy_files) != num_renders)
        #     or (len(metadata_files) != 1)
        # ):
        #     logger.error(
        #         f"Found object {file_identifier} was not rendered successfully!"
        #     )
        #     if failed_log_file is not None:
        #         log_processed_object(
        #             failed_log_file,
        #             file_identifier,
        #             sha256,
        #         )
        #     return False

        # metadata_path = os.path.join(target_directory, "metadata.json")
        # with open(metadata_path, "r", encoding="utf-8") as f:
        #     metadata_file = json.load(f)
        # metadata_file["sha256"] = sha256
        # metadata_file["file_identifier"] = file_identifier
        # metadata_file["save_uid"] = save_uid
        # metadata_file["metadata"] = metadata
        # with open(metadata_path, "w", encoding="utf-8") as f:
        #     json.dump(metadata_file, f, indent=2, sort_keys=True)

        if os.path.exists(frames_dir):
            try:
                shutil.rmtree(frames_dir)
                logger.info(f"Successfully deleted frames directory: {frames_dir}")
            except Exception as e:
                logger.warning(f"Failed to delete frames directory: {e}")

        with zipfile.ZipFile(
            f"{target_directory}.zip", "w", zipfile.ZIP_DEFLATED
        ) as ziph:
            zipdir(target_directory, ziph)

        fs, path = fsspec.core.url_to_fs(render_dir)
        fs.makedirs(os.path.join(path, "renders"), exist_ok=True)
        # 检查目标zip文件是否已存在，如果存在则先删除
        target_zip_path = os.path.join(path, "renders", f"{save_uid}.zip")
        try:
            if fs.exists(target_zip_path):
                logger.info(f"Removing existing zip file: {target_zip_path}")
                fs.rm(target_zip_path)
                logger.info(f"Successfully removed existing zip file")
        except Exception as e:
            logger.warning(f"Failed to remove existing zip file: {e}")
        fs.put(
            os.path.join(f"{target_directory}.zip"),
            os.path.join(path, "renders", f"{save_uid}.zip"), 
        )

        if successful_log_file is not None:
            log_processed_object(successful_log_file, file_identifier, sha256)
        
        # 启动子进程执行 python unzip.py
        unzip_script_path = os.path.join(os.path.dirname(__file__), "unzip.py")
        # 使用Popen启动子进程，不等待其完成
        unzip_process = subprocess.Popen(
            ["python", unzip_script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logger.info(f"Started unzip.py subprocess with PID: {unzip_process.pid}")

        return True


def handle_new_object(
    local_path: str,
    file_identifier: str,
    sha256: str,
    metadata: Dict[str, Any],
    log_file: str = "handle-new-object.csv",
) -> None:
    log_processed_object(log_file, file_identifier, sha256)


def handle_modified_object(
    local_path: str,
    file_identifier: str,
    new_sha256: str,
    old_sha256: str,
    metadata: Dict[str, Any],
    num_renders: int,
    render_dir: str,
    only_northern_hemisphere: bool,
    gpu_devices: Union[int, List[int]],
    render_timeout: int,
) -> None:
    success = handle_found_object(
        local_path=local_path,
        file_identifier=file_identifier,
        sha256=new_sha256,
        metadata=metadata,
        num_renders=num_renders,
        render_dir=render_dir,
        only_northern_hemisphere=only_northern_hemisphere,
        gpu_devices=gpu_devices,
        render_timeout=render_timeout,
        successful_log_file=None,
        failed_log_file=None,
    )

    if success:
        log_processed_object(
            "handle-modified-object-successful.csv",
            file_identifier,
            old_sha256,
            new_sha256,
        )
    else:
        log_processed_object(
            "handle-modified-object-failed.csv",
            file_identifier,
            old_sha256,
            new_sha256,
        )


def handle_missing_object(
    file_identifier: str,
    sha256: str,
    metadata: Dict[str, Any],
    log_file: str = "handle-missing-object.csv",
) -> None:
    log_processed_object(log_file, file_identifier, sha256)


def get_example_objects() -> pd.DataFrame:
    path = os.path.join(os.path.dirname(__file__), "example-objects.json")
    return pd.read_json(path, orient="records")


def load_local_object_paths(object_paths_gz: str) -> Dict[str, str]:
    """Load mapping from object identifier -> local path from a gzipped JSON file.

    The gzipped file is expected to contain a JSON object mapping fileIdentifier -> local_path.
    """
    if not os.path.exists(object_paths_gz):
        raise FileNotFoundError(f"Object paths file not found: {object_paths_gz}")
    with gzip.open(object_paths_gz, "rt", encoding="utf-8") as f:
        mapping = json.load(f)
    return mapping


def get_local_textured_objects(
    objects_file: str,
    object_paths_gz: str,
    n: int = 10,
    start_index: int = 9,
) -> pd.DataFrame:
    """Read objects_with_texture.txt and object-paths.json.gz and return a DataFrame similar to
    what get_random_textured_objects_from_objaverse would return.

    The objects_file should contain one fileIdentifier per line. The object_paths_gz maps
    fileIdentifier -> local_path.
    """
    if not os.path.exists(objects_file):
        raise FileNotFoundError(f"objects file not found: {objects_file}")

    mapping = load_local_object_paths(object_paths_gz)

    with open(objects_file, "r", encoding="utf-8") as f:
        ids = [line.strip() for line in f if line.strip()]

    # Keep only those that exist in the mapping
    available = [fid for fid in ids if fid in mapping]
    if len(available) == 0:
        raise RuntimeError("No local textured objects found in mapping.")
    if start_index < 0:
        raise ValueError(f"start_index must be non-negative, got {start_index}")
    if start_index >= len(available):
        raise ValueError(
            f"start_index {start_index} is out of range. "
            f"Available objects: {len(available)}"
        )
    max_available = len(available) - start_index
    if n > max_available:
        logger.warning(
            f"Requested {n} objects from index {start_index}, "
            f"but only {max_available} available. Using all available."
        )
        n = max_available

    selected = available[start_index:start_index + n]
    logger.info(
        f"Selected {len(selected)} objects from index {start_index} "
        f"to {start_index + len(selected) - 1} (total available: {len(available)})"
    )

    records = []
    for fid in selected:
        records.append({
            "sha256": "",
            "fileIdentifier": fid,
            "source": "local",
            "metadata": {},
            "local_path": "/data1/DATA/graspxl-objaverse/" + mapping[fid],
        })

    df = pd.DataFrame(records)
    return df


def render_objects(
    render_dir: str = "~/.objaverse/renders",
    download_dir: Optional[str] = "~/.objaverse",
    num_renders: int = 81,
    processes: Optional[int] = None,
    save_repo_format: Optional[Literal["zip", "tar", "tar.gz", "files"]] = "files",
    only_northern_hemisphere: bool = False,
    render_timeout: int = 9000,
    gpu_devices: Optional[Union[int, List[int]]] = None,
    # NEW args for local mode
    local_objects_file: Optional[str] = "/data1/DATA/graspxl-objaverse/objects_with_texture.txt",
    object_paths_gz: Optional[str] = "/data1/DATA/graspxl-objaverse/object-paths.json.gz",
    local_n: int = 1,
) -> None:
    if platform.system() not in ["Linux", "Darwin"]:
        raise NotImplementedError(
            f"Platform {platform.system()} is not supported. Use Linux or MacOS."
        )
    if download_dir is None and save_repo_format is not None:
        raise ValueError(
            f"If {save_repo_format=} is not None, {download_dir=} must be specified."
        )

    parsed_gpu_devices: Union[int, List[int]] = 0
    if gpu_devices is None:
        parsed_gpu_devices = len(GPUtil.getGPUs())
    logger.info(f"Using {parsed_gpu_devices} GPU devices for rendering.")

    if processes is None:
        processes = multiprocessing.cpu_count() * 3

    # If local_objects_file and object_paths_gz are provided, use local selection
    if local_objects_file is not None and object_paths_gz is not None:
        logger.info("Selecting objects from local objects_with_texture file")
        objects = get_local_textured_objects(local_objects_file, object_paths_gz, n=local_n)
        logger.info(f"Selected {len(objects)} local objects for rendering.")

        # Filter out already rendered objects in render_dir
        # fs, path = fsspec.core.url_to_fs(render_dir)
        # try:
        #     zip_files = fs.glob(os.path.join(path, "renders", "*.zip"), refresh=True)
        # except TypeError:
        #     zip_files = fs.glob(os.path.join(path, "renders", "*.zip"))
        # saved_ids = set(zip_file.split("/")[-1].split(".")[0] for zip_file in zip_files)

        # objects["saveUid"] = objects["fileIdentifier"].apply(get_uid_from_str)
        # objects = objects[~objects["saveUid"].isin(saved_ids)]
        # objects = objects.reset_index(drop=True)
        # logger.info(f"Rendering {len(objects)} new local objects.")

        # Iterate and call handle_found_object directly using local paths
        for _, row in objects.iterrows():
            local_path = row.get("local_path")
            file_identifier = row.get("fileIdentifier")
            sha256 = row.get("sha256", "")
            metadata = row.get("metadata", {}) or {}
            try:
                success = handle_found_object(
                    local_path=local_path,
                    file_identifier=file_identifier,
                    sha256=sha256,
                    metadata=metadata,
                    num_renders=num_renders,
                    render_dir=render_dir,
                    only_northern_hemisphere=only_northern_hemisphere,
                    gpu_devices=parsed_gpu_devices,
                    render_timeout=render_timeout,
                )
                if not success:
                    logger.error(f"Rendering failed for {file_identifier}")
            except Exception as e:
                logger.exception(f"Error while rendering {file_identifier}: {e}")
        return

    else:
        raise ValueError(
            "Both local_objects_file and object_paths_gz must be provided for local rendering."
        )


if __name__ == "__main__":
    fire.Fire(render_objects)
