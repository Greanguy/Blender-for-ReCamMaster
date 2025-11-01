# from objaverse import DownloadObjaverse
import multiprocessing
import random
from glob import  glob
# import open3d as o3d
import os
from tqdm import tqdm
import argparse
from objaverse import DownloadObjaverse
import trimesh


# parser = argparse.ArgumentParser(description="Process some integers.")
# parser.add_argument('--num', type=int, default=0, required=True, help='which machine')
# parser.add_argument('--template', type=int, default=0, required=True, help='which machine')
# args = parser.parse_args()


# download
with open('./graspxl_sketchfab.txt', 'r') as file_list:
    list_f = file_list.readlines()

uids = []
for file in list_f:
    uids.append(file.strip())


# template = args.template
uids = sorted(uids)
# uids = uids[args.num*template:(args.num+1)*template]

uids = uids
# print(uids[:5])
processes = multiprocessing.cpu_count()

down_objaverse = DownloadObjaverse(download_path='/data1/DATA/graspxl-objaverse')
# down_objaverse = DownloadObjaverse(download_path='/nasdata/yyk/temp/objaverse')

objects = down_objaverse.load_objects(
    uids=uids,
    download_processes=processes
)

print("FINISH! Downloaded", len(objects), "objects")


# gld转obj文件

# def convert_glb_to_obj(glb_path, obj_path):
#     # 读取 GLB 文件
#     mesh = o3d.io.read_triangle_mesh(glb_path)

#     # 检查 mesh 是否有效
#     if not mesh.is_empty():
#         # 将 OBJ 文件写入
#         o3d.io.write_triangle_mesh(obj_path, mesh)

#         base_name = os.path.splitext(obj_path)[0]  # 去掉扩展名
#         mtl_file = base_name + '.mtl'
#         if os.path.exists(mtl_file):
#             os.remove(mtl_file)
        
#     else:
#         print("Failed to read the mesh from the GLB file.")

# def remove():
#     pngs = glob('/NASdata2/objaverse/objaverse/objs/*.png')
#     for png in pngs:
#         os.remove(png)
    
#     mtls = glob('/NASdata2/objaverse/objaverse/objs/*.mtl')
#     for mtl in mtls:
#         os.remove(mtl)

# objaverse_path = '/NASdata2/objaverse/objaverse/glbs/*/*.glb'
# all_paths = glob(objaverse_path)

# all_paths = all_paths[:30000]

# for i in tqdm(range(len(all_paths))):
#     glb_path = all_paths[i]

#     file_name = glb_path.split('/')[-1][:-4]
#     obj_path = f'/NASdata2/objaverse/objaverse/objs/{file_name}.obj'
#     if os.path.exists(obj_path):
#         continue
#     convert_glb_to_obj(glb_path, obj_path)

#     if i % 100 ==0:
#         remove()

# remove()




