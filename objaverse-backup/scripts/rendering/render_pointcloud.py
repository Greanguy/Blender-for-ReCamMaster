import open3d as o3d
import numpy as np
import imageio.v2 as imageio
import os
import datetime
from open3d.visualization import rendering

# ====== 配置区域 ======
PLY_PATH   = "/data1/xzf_data/test_data/litevggt_counter.ply"   # TODO: 换成你的 ply 路径

WIDTH, HEIGHT = 1280, 720
FPS      = 30
DURATION = 8
N_FRAMES = FPS * DURATION

# 控制“看起来多大”的尺度因子：越小越近，物体越大
RADIUS_SCALE = 0.8
# =====================

# === 根据 PLY 文件名 + 时间戳，动态生成不冲突的输出路径 ===
base_name = os.path.splitext(os.path.basename(PLY_PATH))[0]
run_tag   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

OUT_DIR    = f"frames_{base_name}_{run_tag}"
VIDEO_PATH = f"{base_name}_orbit_{run_tag}.mp4"

os.makedirs(OUT_DIR, exist_ok=True)
print("Frames will be saved to:", OUT_DIR)
print("Video will be saved to :", VIDEO_PATH)

# 1. 读取点云
pcd = o3d.io.read_point_cloud(PLY_PATH)
print(pcd)
print("Has colors:", pcd.has_colors())

if not pcd.has_colors():
    # 在白背景上稍微深一点
    pcd.paint_uniform_color([0.2, 0.5, 0.9])

# ================== 法向估计（优化版） ==================
num_points = np.asarray(pcd.points).shape[0]
print(f"Point count: {num_points}")

# 千万级点云不要做全局一致化，否则基本跑不完
print("Estimating normals (fast mode for large point cloud)...")

if num_points > 2_000_000:
    # 大点云：只用 KNN 做局部法向估计，不做 orient_normals_consistent_tangent_plane
    # KNN 不依赖半径，对分布更鲁棒；邻居数量控制在 16 左右即可产生平滑法向
    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamKNN(knn=16)
    )
else:
    # 小点云：可以用稍微精细一点的设置（可选）
    bbox_for_normals = pcd.get_axis_aligned_bounding_box()
    extent_normals   = bbox_for_normals.get_extent()
    diag             = np.linalg.norm(extent_normals)

    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(
            radius=diag * 0.05,
            max_nn=64
        )
    )
    # 只有在点数不太大时才做全局一致化
    pcd.orient_normals_consistent_tangent_plane(50)

# 法向归一化一下（虽然大部分情况下内部会做，这里显式一下）
pcd.normalize_normals()
# =====================================================

# 2. 创建离屏渲染器（不会创建窗口）
renderer = rendering.OffscreenRenderer(WIDTH, HEIGHT)

# 白色背景
renderer.scene.set_background([1.0, 1.0, 1.0, 1.0])  # RGBA

# 点云材质
mat = rendering.MaterialRecord()
# 使用带光照的 shader + 法向信息，模拟“单侧效果”
mat.shader = "defaultLit"
mat.point_size = 2.0

renderer.scene.add_geometry("pcd", pcd, mat)

# 3. 相机绕点云中心一周
bbox   = pcd.get_axis_aligned_bounding_box()
center = bbox.get_center()
extent = bbox.get_extent()

# 相机距离，根据点云尺度 + 缩放因子
radius = np.linalg.norm(extent) * RADIUS_SCALE

# 上方向设为 -Y，保证画面不再上下颠倒
up = np.array([0.0, -1.0, 0.0])

images = []
print("Rendering frames...")

for i in range(N_FRAMES):
    theta = 2.0 * np.pi * i / N_FRAMES

    # 水平绕圈 + 稍微抬高
    eye = center + radius * np.array([
        np.cos(theta),
        0.2,
        np.sin(theta)
    ])

    renderer.scene.camera.look_at(center, eye, up)

    img_o3d = renderer.render_to_image()
    img = np.asarray(img_o3d)

    frame_path = os.path.join(OUT_DIR, f"frame_{i:04d}.png")
    imageio.imwrite(frame_path, img)
    images.append(img)

    if i % 30 == 0:
        print(f"  frame {i}/{N_FRAMES}")

print("Writing video to", VIDEO_PATH)
imageio.mimsave(
    VIDEO_PATH,
    images,
    fps=FPS,
    codec="libx264",
    quality=8,
)
print("Done!")
