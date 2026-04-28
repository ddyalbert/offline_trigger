import os
from PyQt5.QtWidgets import QFileDialog, QApplication
from pathlib import Path

def get_workspace_path(path_name, root_file = [".gitignore", "main.py"]):

    current_dir = Path(path_name).parent
    workspace_path = None
    for pp in [current_dir] + list(current_dir.parents):
        if any((pp / ff).exists() for ff in root_file):
            workspace_path = pp
            break

    if workspace_path is None:
        print("myError(get_workspace_path): Can't find workspace path, please check the root_file.")

    return str(workspace_path)


def get_file(parent_window = None, filter="All file(*.*)" , title="Choose a file", default_dir = "/home/duandy/disk/bolometer/Data/"):
    
    # 确保.temp目录存在
    workspace_path = Path(__file__).parent.parent
    temp_dir = workspace_path / ".temp"
    temp_dir.mkdir(exist_ok=True)
    
    memory_file = temp_dir / ".filepath.txt"
    
    # 读取上次使用的路径
    initial_dir = ""
    if memory_file.exists():
        try:
            with open(memory_file, 'r', encoding='utf-8') as f:
                initial_dir = f.read().strip()
                if not os.path.exists(initial_dir):
                    initial_dir = ""
        except:
            initial_dir = ""
    
    if initial_dir == "":
        initial_dir = default_dir
    
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    file_path, _ = QFileDialog.getOpenFileName(parent_window, title, initial_dir, filter)
    
    # 保存选择的路径到记忆文件
    if file_path:
        try:
            with open(memory_file, 'w', encoding='utf-8') as f:
                directory = str(Path(file_path).parent)
                f.write(directory)
        except:
            pass
        
        return str(file_path)
    else:
        return ""
    
def extract_file_info(file_path: str):
    # such as "/home/duandy/disk/bolometer/Data/20230801_123456.BIN2"
    # return "/home/duandy/disk/bolometer/Data/", "20230801_123456", ".BIN2"
    path_obj = Path(file_path)
    file_dir = str(path_obj.parent) + "/"
    file_name = str(path_obj.stem)
    file_ext = str(path_obj.suffix)
    
    return file_dir, file_name, file_ext
    
if __name__ == "__main__":
    file_path, file_info = get_file()
    print(file_path)
    print(file_info)