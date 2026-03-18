import os
import json
from cryptography.fernet import Fernet
import base64
import hashlib

# 核心文件列表
CORE_FILES = [
    'backend/app/services/agent_profiles.py',
    '.env'
]

# 生成加密密钥
def generate_key(password):
    """从密码生成加密密钥"""
    # 使用 SHA-256 生成 32 字节的密钥
    key = hashlib.sha256(password.encode()).digest()
    # 编码为 base64
    return base64.urlsafe_b64encode(key)

# 加密文件
def encrypt_file(file_path, key):
    """加密文件"""
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        
        fernet = Fernet(key)
        encrypted_data = fernet.encrypt(data)
        
        # 保存加密文件
        encrypted_file_path = file_path + '.encrypted'
        with open(encrypted_file_path, 'wb') as f:
            f.write(encrypted_data)
        
        print(f"已加密文件: {file_path} -> {encrypted_file_path}")
        return True
    except Exception as e:
        print(f"加密文件时出错 {file_path}: {e}")
        return False

# 主函数
def main():
    print("开始加密核心文件...")
    
    # 使用默认密码（实际应用中应该使用更安全的方式）
    password = "traceback_secure_password_2026"
    print("使用默认密码进行加密...")
    
    # 生成密钥
    key = generate_key(password)
    
    # 保存密钥到安全位置（仅用于演示，实际应用中应该使用更安全的方式）
    key_file = 'encryption_key.txt'
    with open(key_file, 'wb') as f:
        f.write(key)
    print(f"密钥已保存到: {key_file}")
    
    # 加密核心文件
    for file_path in CORE_FILES:
        if os.path.exists(file_path):
            encrypt_file(file_path, key)
        else:
            print(f"文件不存在: {file_path}")
    
    print("加密完成！")

if __name__ == "__main__":
    main()
