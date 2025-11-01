"""Blender script for visualizing camera setups from extrinsics.json."""

import bpy
import os
import json
import numpy as np
from mathutils import Matrix, Vector
import math

# 清除当前场景
def reset_scene():
    # 删除所有对象
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    
    # 清除所有材质
    for material in bpy.data.materials:
        bpy.data.materials.remove(material, do_unlink=True)

# 相机外参解析函数
def parse_matrix(matrix_str):
    rows = matrix_str.strip().split('] [')
    matrix = []
    for row in rows:
        row = row.replace('[', '').replace(']', '')
        if len((list(map(float, row.split())))) == 3:
            matrix.append((list(map(float, row.split()))) + [0.])
        else:
            matrix.append(list(map(float, row.split())))
    return np.array(matrix)

# 计算相机到世界的转换矩阵
def get_c2w(w2cs, transform_matrix, relative_c2w=True):
    if relative_c2w:
        target_cam_c2w = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ])
        abs2rel = target_cam_c2w @ w2cs[0]
        ret_poses = [target_cam_c2w, ] + [abs2rel @ np.linalg.inv(w2c) for w2c in w2cs[1:]]
    else:
        ret_poses = [np.linalg.inv(w2c) for w2c in w2cs]
    ret_poses = [transform_matrix @ x for x in ret_poses]
    return np.array(ret_poses, dtype=np.float32)

# 设置相机参数
def set_camera_from_c2w_matrix(cam, c2w_matrix):
    # 确保是4x4矩阵
    if c2w_matrix.shape == (3, 4):
        c2w_matrix = np.vstack([c2w_matrix, np.array([0, 0, 0, 1])])
    
    # 转换为Blender的Matrix对象
    mat = Matrix(
        ((c2w_matrix[0, 0], c2w_matrix[0, 1], c2w_matrix[0, 2], c2w_matrix[0, 3]),
         (c2w_matrix[1, 0], c2w_matrix[1, 1], c2w_matrix[1, 2], c2w_matrix[1, 3]),
         (c2w_matrix[2, 0], c2w_matrix[2, 1], c2w_matrix[2, 2], c2w_matrix[2, 3]),
         (0, 0, 0, 1))
    )
    
    # 设置相机的matrix_world
    cam.matrix_world = mat

# 创建相机
def create_camera(name="Camera"):
    # 创建相机数据
    cam_data = bpy.data.cameras.new(name=name)
    cam_data.lens = 10
    cam_data.sensor_width = 32
    
    # 创建相机对象
    cam = bpy.data.objects.new(name, cam_data)
    bpy.context.collection.objects.link(cam)
    return cam

# 创建相机可视化对象
def create_camera_visualization(cam, name, color):
    # 创建一个锥形物体表示相机视野
    bpy.ops.mesh.primitive_cone_add(
        vertices=4,
        radius1=0.1,
        radius2=0,
        depth=0.2,
        location=(0, 0, 0)
    )
    cone = bpy.context.active_object
    cone.name = f"Cone_{name}"
    
    # 旋转锥体使其朝向-Z方向（相机方向）
    cone.rotation_euler = (math.pi, 0, 0)
    
    # 设置锥体的父对象为相机
    cone.parent = cam
    
    # 设置锥体材质颜色
    mat = bpy.data.materials.new(name=f"CameraMat_{name}")
    mat.diffuse_color = (*color, 0.5)  # RGBA
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    principled_bsdf = nodes.get("Principled BSDF")
    principled_bsdf.inputs["Base Color"].default_value = (*color, 1)
    principled_bsdf.inputs["Alpha"].default_value = 0.5
    
    # 应用材质到锥体
    if cone.data.materials:
        cone.data.materials[0] = mat
    else:
        cone.data.materials.append(mat)
    
    return cone

# 创建中心参考对象
def create_center_reference():
    bpy.ops.mesh.primitive_ico_sphere_add(radius=0.05, location=(0, 2, 0))
    sphere = bpy.context.active_object
    sphere.name = "SceneCenter"
    
    # 添加材质
    mat = bpy.data.materials.new(name="CenterMat")
    mat.diffuse_color = (1, 0, 1, 1)  # 红色
    if sphere.data.materials:
        sphere.data.materials[0] = mat
    else:
        sphere.data.materials.append(mat)
    
    return sphere

# 创建相机路径曲线
def create_camera_path(c2ws):
    # 创建一条曲线用于显示相机路径
    curve_data = bpy.data.curves.new('CameraPath', type='CURVE')
    curve_data.dimensions = '3D'
    
    # 添加样条线
    polyline = curve_data.splines.new('NURBS')
    polyline.points.add(len(c2ws)-1)  # 已经有一个点，所以减1
    
    # 设置曲线点位置
    for i, c2w in enumerate(c2ws):
        if i < len(polyline.points):
            point = polyline.points[i]
            point.co = (c2w[0, 3], c2w[1, 3], c2w[2, 3], 1)
    
    # 创建曲线对象
    curve_obj = bpy.data.objects.new('CameraPath', curve_data)
    bpy.context.collection.objects.link(curve_obj)
    
    # 设置曲线属性
    curve_data.bevel_depth = 0.005
    curve_data.resolution_u = 12
    curve_data.use_fill_caps = True
    
    # 添加材质
    mat = bpy.data.materials.new(name="PathMat")
    mat.diffuse_color = (0, 0.8, 0.8, 1)  # 青色
    if curve_obj.data.materials:
        curve_obj.data.materials[0] = mat
    else:
        curve_obj.data.materials.append(mat)
    
    return curve_obj

# 主函数
def main():
    # 重置场景
    reset_scene()
    
    # 创建中心参考对象
    create_center_reference()
    
    # 设置渲染属性
    bpy.context.scene.render.resolution_x = 832
    bpy.context.scene.render.resolution_y = 480
    
    # 加载相机参数
    extrinsics_path = 'C:/Users/user/Desktop/extrinsics.json'
    if not os.path.exists(extrinsics_path):
        print(f"错误: 找不到文件 {extrinsics_path}")
        print(f"请将extrinsics.json放在与此脚本相同目录下")
        raise RuntimeError("failed")
        return
        
    with open(extrinsics_path, 'r') as file:
        data = json.load(file)
    
    # 处理相机参数
    cameras_data = [parse_matrix(data[f"frame{i}"][f"cam09"]) for i in range(0, 81, 1)]
    cameras_data = np.transpose(np.stack(cameras_data), (0, 2, 1))
    w2cs = []
    for cam_data in cameras_data:
        if cam_data.shape[0] == 3:
            cam_data = np.vstack((cam_data, np.array([[0, 0, 0, 1]])))
        cam_data = cam_data[:, [1, 2, 0, 3]]
        cam_data[:3, 1] *= -1.
        cam_data[:3, 3] /= 100
        w2cs.append(np.linalg.inv(cam_data))
    
    transform_matrix = np.array([[-1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
    c2ws = get_c2w(w2cs, transform_matrix, True)
    flip_z_rotation = np.array([
    [0, 1, 0, 0],
    [-1, 0, 0, 0],
    [0, 0, 1, 0],
    [0, 0, 0, 1]
    ])

    # 对每个相机的c2w矩阵应用水平镜像变换
#    for i in range(len(c2ws)):
#        c2ws[i] = flip_z_rotation @ c2ws[i]
        
    # 缩放相机位置
#    scale = max(max(abs(c2w[:3, 3])) for c2w in c2ws)
#    if scale > 1e-3:
#        for c2w in c2ws:
#            c2w[:3, 3] /= scale
    
    # 创建相机路径
    create_camera_path(c2ws)
    
    # 创建并设置所有相机
    cameras = []
    for i, c2w in enumerate(c2ws):
        # 创建一个相机
        cam = create_camera(f"Camera_{i:03d}")
        
        # 设置相机参数
        set_camera_from_c2w_matrix(cam, c2w)
#        cam.location.z *= -1
        cam.rotation_euler.x *= -1
#        cam.rotation_euler.x += math.radians(180)
        
        # 创建相机可视化
        # 根据索引生成不同颜色
        color = ((i % 9) / 8, ((i // 9) % 9) / 8, ((i // 81) % 9) / 8)
        vis = create_camera_visualization(cam, f"{i:03d}", color)
        
        cameras.append(cam)
        
        # 如果是第一个相机，设为活动相机
        if i == 0:
            bpy.context.scene.camera = cam
    
    # 添加一个空物体作为所有相机的目标点
    bpy.ops.object.empty_add(type='SPHERE', location=(0, -2, 0))
    target = bpy.context.active_object
    target.name = "CameraTarget"
    target.empty_display_size = 0.05
    
    # 选择第一个相机
    bpy.context.view_layer.objects.active = cameras[0]
    for obj in bpy.data.objects:
        obj.select_set(False)
    cameras[0].select_set(True)
    
    print(f"已创建并可视化 {len(cameras)} 个相机")
    print("使用Blender的视图菜单切换到相机视图(Numpad 0)查看各相机视角")

if __name__ == "__main__":
    main()