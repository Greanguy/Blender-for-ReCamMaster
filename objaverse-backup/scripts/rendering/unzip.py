import os
import zipfile
import glob

def extract_zip_files(target_dir=None):
    """
    解压ZIP文件
    
    Args:
        target_dir: 目标目录，如果为None则使用默认目录
    """
    # 设置目标目录
    if target_dir is None:
        target_dir = "/home/xu_zifan/.objaverse/renders/renders"
    
    # 确保目标目录存在
    if not os.path.exists(target_dir):
        print(f"目标目录不存在: {target_dir}")
        return
    
    # 切换到目标目录
    original_dir = os.getcwd()
    os.chdir(target_dir)
    print(f"工作目录已切换到: {target_dir}")
    
    try:
        # 记录新解压文件夹的文件
        record_file = "extracted_folders.txt"
        
        # 清空或创建记录文件
        with open(record_file, 'w') as f:
            f.write("")  # 清空文件内容
        
        # 获取当前目录下所有的.zip文件
        zip_files = glob.glob("*.zip")
        
        if not zip_files:
            print("没有找到ZIP文件")
            return
        
        print(f"找到 {len(zip_files)} 个ZIP文件")
        
        # 记录处理的文件夹(包括新建和更新的)
        processed_folders = []
        
        # 遍历所有ZIP文件
        for zip_path in zip_files:
            # 获取ZIP文件的名称(不含扩展名)
            zip_name = os.path.splitext(zip_path)[0]
            
            try:
                print(f"正在解压: {zip_path}")
                
                # 创建或使用现有的目标文件夹
                extract_path = os.path.join(target_dir, zip_name)
                
                # 如果文件夹已存在,提示将合并内容
                if os.path.exists(extract_path):
                    print(f"文件夹 {zip_name} 已存在,将合并内容...")
                else:
                    print(f"创建新文件夹: {zip_name}")
                
                # 解压ZIP文件(会自动覆盖同名文件,新文件会添加进去)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
                
                print(f"成功解压到: {zip_name}")
                processed_folders.append(zip_name)
                
            except Exception as e:
                print(f"解压 {zip_path} 时出错: {str(e)}")
        
        # 将处理的文件夹名称写入记录文件
        if processed_folders:
            with open(record_file, 'w', encoding='utf-8') as f:
                for folder in processed_folders:
                    f.write(folder + '\n')
            print(f"\n已处理 {len(processed_folders)} 个文件夹")
            print(f"文件夹列表已保存到: {record_file}")
        else:
            print("\n没有需要解压的ZIP文件")
    
    finally:
        # 恢复原始工作目录
        os.chdir(original_dir)
        print(f"工作目录已恢复到: {original_dir}")

if __name__ == "__main__":
    extract_zip_files()