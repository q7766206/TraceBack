import py_compile
import os

# 核心文件列表
CORE_FILES = [
    'backend/app/services/agent_profiles.py'
]

# 编译文件为 .pyc
def compile_file(file_path):
    """编译 Python 文件为 .pyc"""
    try:
        py_compile.compile(file_path, doraise=True)
        print(f"已编译文件: {file_path}")
        return True
    except Exception as e:
        print(f"编译文件时出错 {file_path}: {e}")
        return False

# 主函数
def main():
    print("开始编译核心文件...")
    
    for file_path in CORE_FILES:
        if os.path.exists(file_path):
            compile_file(file_path)
        else:
            print(f"文件不存在: {file_path}")
    
    print("编译完成！")
    print("编译后的 .pyc 文件位于 __pycache__ 目录中")

if __name__ == "__main__":
    main()
