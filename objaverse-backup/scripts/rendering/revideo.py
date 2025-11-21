import os
import subprocess
import tempfile
from pathlib import Path

def create_static_video_from_first_frame(
    input_video_path: str,
    output_video_path: str,
    num_frames: int = 81,
    fps: int = 30
) -> bool:
    """
    从输入视频中提取第1帧，复制指定次数后生成新视频（使用ffmpeg）
    
    Args:
        input_video_path: 输入视频路径
        output_video_path: 输出视频路径
        num_frames: 输出视频的帧数
        fps: 输出视频的帧率
        
    Returns:
        bool: 是否成功生成视频
    """
    try:
        # 检查输入视频是否存在
        if not os.path.exists(input_video_path):
            print(f"错误: 输入视频不存在: {input_video_path}")
            return False
        
        # 创建临时目录存储提取的第一帧
        with tempfile.TemporaryDirectory() as temp_dir:
            first_frame_path = os.path.join(temp_dir, "frame_000.png")
            
            # 使用ffmpeg提取第一帧
            extract_cmd = [
                "ffmpeg",
                "-i", input_video_path,
                "-vframes", "1",  # 只提取一帧
                "-y",  # 覆盖输出文件
                first_frame_path
            ]
            
            print(f"正在提取第一帧...")
            result = subprocess.run(
                extract_cmd,
                check=True,
                capture_output=True,
                text=True
            )
            
            if not os.path.exists(first_frame_path):
                print(f"错误: 无法提取第一帧")
                return False
            
            print(f"成功提取第一帧: {first_frame_path}")
            
            # 复制第一帧为多个文件
            print(f"正在复制帧，共 {num_frames} 帧...")
            for i in range(1, num_frames):
                frame_path = os.path.join(temp_dir, f"frame_{i:03d}.png")
                # 使用硬链接或复制
                try:
                    os.link(first_frame_path, frame_path)
                except:
                    # 如果硬链接失败，使用复制
                    import shutil
                    shutil.copy2(first_frame_path, frame_path)
                
                if (i + 1) % 10 == 0:
                    print(f"已复制 {i + 1}/{num_frames} 帧")
            
            # 使用ffmpeg将图片序列转换为视频
            input_pattern = os.path.join(temp_dir, "frame_%03d.png")
            
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",  # 覆盖输出文件
                "-framerate", str(fps),  # 帧率
                "-start_number", "0",  # 起始帧编号
                "-i", input_pattern,  # 输入图片模式
                "-frames:v", str(num_frames),  # 限制帧数
                "-c:v", "libx264",  # 视频编码器
                "-pix_fmt", "yuv420p",  # 像素格式
                "-crf", "23",  # 质量参数
                output_video_path
            ]
            
            print(f"正在生成视频...")
            subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
            
            print(f"成功生成视频: {output_video_path}")
            return True
        
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg命令执行失败: {e.stderr}")
        return False
    except FileNotFoundError:
        print("错误: 未找到ffmpeg，请确保已安装ffmpeg并添加到系统PATH中")
        return False
    except Exception as e:
        print(f"生成视频时出错: {str(e)}")
        return False


def process_directory(base_dir: str = "/home/xu_zifan/.objaverse/renders/renders"):
    """
    处理指定目录下的所有子目录中的cam01.mp4视频
    
    Args:
        base_dir: 基础目录路径
    """
    base_path = Path(base_dir)
    
    if not base_path.exists():
        print(f"错误: 目录不存在: {base_dir}")
        return
    
    # 查找所有包含cam01.mp4的videos目录
    processed_count = 0
    failed_count = 0
    
    for video_dir in base_path.glob("*/videos"):
        cam01_path = video_dir / "cam01.mp4"
        
        if cam01_path.exists():
            cam00_path = video_dir / "cam00.mp4"
            
            # 如果cam00.mp4已存在，跳过
            if cam00_path.exists():
                print(f"\n跳过（已存在）: {video_dir}")
                continue
            
            print(f"\n处理目录: {video_dir}")
            print(f"输入视频: {cam01_path}")
            print(f"输出视频: {cam00_path}")
            
            success = create_static_video_from_first_frame(
                str(cam01_path),
                str(cam00_path),
                num_frames=81,
                fps=30
            )
            
            if success:
                processed_count += 1
            else:
                failed_count += 1
    
    print(f"\n处理完成!")
    print(f"成功: {processed_count} 个")
    print(f"失败: {failed_count} 个")


def process_single_directory(target_dir: str):
    """
    处理单个指定目录
    
    Args:
        target_dir: 目标目录路径（例如：/home/xu_zifan/.objaverse/renders/renders/9a3e80be-3eb8-5beb-987c-bcb7e2316a57）
    """
    videos_dir = Path(target_dir) / "videos"
    
    if not videos_dir.exists():
        print(f"错误: videos目录不存在: {videos_dir}")
        return
    
    cam01_path = videos_dir / "cam01.mp4"
    cam00_path = videos_dir / "cam001.mp4"
    
    if not cam01_path.exists():
        print(f"错误: cam01.mp4不存在: {cam01_path}")
        return
    
    print(f"输入视频: {cam01_path}")
    print(f"输出视频: {cam00_path}")
    
    success = create_static_video_from_first_frame(
        str(cam01_path),
        str(cam00_path),
        num_frames=81,
        fps=30
    )
    
    if success:
        print("处理成功!")
    else:
        print("处理失败!")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 如果提供了命令行参数，处理指定目录
        target_dir = sys.argv[1]
        print(f"处理单个目录: {target_dir}")
        process_single_directory(target_dir)
    else:
        # 否则处理所有目录
        print("处理所有目录...")
        process_directory()