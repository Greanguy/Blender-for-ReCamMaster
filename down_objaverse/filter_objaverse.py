import trimesh
from tqdm import tqdm
import multiprocessing as mp
from functools import partial
from objaverse import DownloadObjaverse


def has_texture(scene):
    """检查是否有UV坐标"""
    if isinstance(scene, trimesh.Scene):
        for geometry in scene.geometry.values():
            if not isinstance(geometry, trimesh.Trimesh):
                continue
            if hasattr(geometry.visual, 'uv') and geometry.visual.uv is not None:
                return True
    elif hasattr(scene.visual, 'uv') and scene.visual.uv is not None:
        return True
    
    return False

def check_single_object(item):
    """检查单个对象（用于多进程）"""
    key, local_path = item
    try:
        scene = trimesh.load(local_path)
        if has_texture(scene):
            return key
        return None
    except Exception as e:
        print(f"Error loading {key}: {e}")
        return None

def get_objects():
    with open('./graspxl_sketchfab.txt', 'r') as file_list:
        list_f = file_list.readlines()
    uids = []
    for file in list_f:
        uids.append(file.strip())
    uids = sorted(uids)
    processes = mp.cpu_count()
    down_objaverse = DownloadObjaverse(download_path='/data1/DATA/graspxl-objaverse')
    objects = down_objaverse.load_objects(
        uids=uids,
        download_processes=processes
    )
    print("FINISH! Downloaded", len(objects), "objects")
    return objects

# 使用多进程
if __name__ == "__main__":
    objects = get_objects()
    items = list(objects.items())
    
    # 创建进程池
    num_processes = 8
    with mp.Pool(processes=num_processes) as pool:
        results = list(tqdm(
            pool.imap(check_single_object, items),
            total=len(items),
            desc="Checking textures"
        ))
    
    # 过滤出有纹理的keys
    textured_keys = [key for key in results if key is not None]
    
    print(f"Found {len(textured_keys)} objects with texture")
    
    # 保存结果
    filtered_file_path = "/data1/DATA/graspxl-objaverse/objects_with_texture.txt"
    with open(filtered_file_path, 'w') as f:
        for key in textured_keys:
            f.write(key + '\n')