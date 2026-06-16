import os
import sys
import tempfile

def get_app_dir():
    """取得應用程式 exe 所在目錄 (PyInstaller) 或專案根目錄 (開發環境)"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包環境：exe 所在目錄
        return os.path.dirname(sys.executable)
    else:
        # 開發環境：src 的父目錄（專案根目錄）
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_temp_dir(subdir_name="de_temp"):
    """取得可寫入的臨時目錄"""
    temp_base = tempfile.gettempdir()
    temp_dir = os.path.join(temp_base, subdir_name)
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir

def get_node_path():
    """取得 Node.js portable 執行檔的絕對路徑"""
    if getattr(sys, 'frozen', False):
        # 優先檢查是否在單一檔案 (onefile) 模式下的臨時目錄 sys._MEIPASS
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            node_in_meipass = os.path.join(meipass, "node", "node.exe")
            if os.path.exists(node_in_meipass):
                return node_in_meipass
            node_in_meipass_direct = os.path.join(meipass, "node.exe")
            if os.path.exists(node_in_meipass_direct):
                return node_in_meipass_direct

        # 備用：onedir 打包後環境，檢查 _internal/node/node.exe
        base_dir = os.path.dirname(sys.executable)
        internal_node = os.path.join(base_dir, "_internal", "node", "node.exe")
        if os.path.exists(internal_node):
            return internal_node
        
        # 備用：檢查 _internal/node.exe
        internal_node_direct = os.path.join(base_dir, "_internal", "node.exe")
        if os.path.exists(internal_node_direct):
            return internal_node_direct
        
        # 備用：與 exe 同目錄
        same_dir_node = os.path.join(base_dir, "node.exe")
        if os.path.exists(same_dir_node):
            return same_dir_node
        
        return "node"
    else:
        # 開發環境：檢查專案根目錄下的 node/node.exe
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        dev_node = os.path.join(project_dir, "node", "node.exe")
        if os.path.exists(dev_node):
            return dev_node
        
        return "node"

def get_resource_path(relative_path):
    """
    取得相容開發環境與 PyInstaller 打包環境 (含 _MEIPASS 臨時目錄) 的資源路徑
    """
    if getattr(sys, 'frozen', False):
        # 如果是 PyInstaller 單一檔案模式，資源會被解壓到 sys._MEIPASS
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            path = os.path.join(meipass, relative_path)
            if os.path.exists(path):
                return path
        # 備用：如果是 Onedir 模式，在 exe 同級或 _internal 下
        base_dir = os.path.dirname(sys.executable)
        path = os.path.join(base_dir, "_internal", relative_path)
        if os.path.exists(path):
            return path
        path = os.path.join(base_dir, relative_path)
        if os.path.exists(path):
            return path
            
    # 開發環境：專案根目錄下的相對路徑
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, relative_path)
