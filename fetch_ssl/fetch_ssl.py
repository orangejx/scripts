import hvac
import json
import os
import sys
import time
import logging
from dotenv import load_dotenv


# 指定 .env 文件的路径
dotenv_path = './.env'
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f".env 文件已加载")
else:
    print(f"读取.env文件时出错")
    sys.exit(1)

# 读取环境变量
# Vault 服务器的 URL 和 Token
VAULT_URL = os.getenv('VAULT_URL')
VAULT_TOKEN = os.getenv('VAULT_TOKEN')
VAULT_PATHS_FILE = os.getenv('VAULT_PATHS_FILE')
OUTPUT_DIR = os.getenv('OUTPUT_DIR')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '604800'))  # 默认为一周 
LOG_FILE = os.getenv('LOG_FILE')
CERT_NAME = os.getenv('CERT_NAME')
KEY_NAME = os.getenv('KEY_NAME')
CA_NAME = os.getenv('CA_NAME')

# 配置日志记录
logging.basicConfig(filename=LOG_FILE,
                    level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def log_and_print(message, level='info'):
    """
    同时记录日志并输出到控制台
    """
    # 输出到控制台
    print(message)
    
    # 根据日志级别记录日志
    if level == 'info':
        logging.info(message)
    elif level == 'warning':
        logging.warning(message)
    elif level == 'error':
        logging.error(message)
    elif level == 'debug':
        logging.debug(message)
    else:
        logging.error(f"Unknown log level: {level}. Message: {message}")

def read_cert_list(file_path):
    """从 JSON 文件中读取证书列表及其版本信息"""
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        log_and_print(f"读取证书列表文件时出错: {e}", 'error')
        return {}

def write_cert_list(file_path, data):
    """将更新后的证书配置信息和版本信息写入 JSON 文件"""
    try:
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        log_and_print(f"写入证书列表文件时出错: {e}", 'error')

def setup_vault_client():
    """设置 Vault 客户端"""
    return hvac.Client(url=VAULT_URL, token=VAULT_TOKEN)

def get_local_version(cert_info):
    """从本地证书信息中获取版本"""
    version_str = cert_info.get('version', '')
    try:
        return int(version_str)
    except ValueError:
        return None

def fetch_and_save_certificates(vault_client, domain, mount_point, path, cert_info):
    """从 Vault 获取证书、密钥和 CA, 并保存到本地文件"""
    try:
        local_version = get_local_version(cert_info)
        vault_params = {
            "mount_point": mount_point,
            "path": path
        }
        fetch_latest = True
        
        if local_version is not None:
            # 获取 Vault 数据的当前版本
            secret_metadata = vault_client.secrets.kv.v2.read_secret_metadata(**vault_params)
            current_version = secret_metadata['data']['current_version']
            if current_version == local_version:
                fetch_latest = False
            else:
                # 设置需要获取的版本 
                vault_params['version'] = current_version
                
        
        vault_params["raise_on_deleted_version"] = True  # 避免访问已删除版本时报错
        if fetch_latest:
            # 获取 Vault 数据的指定版本
            secret = vault_client.secrets.kv.v2.read_secret_version(**vault_params)
            data = secret['data']['data']
            current_version = secret['data']['metadata']['version']
            
            # 创建域名目录
            domain_dir = os.path.join(OUTPUT_DIR, domain)
            os.makedirs(domain_dir, exist_ok=True)
            
            # 保存证书、密钥和 CA 到文件
            cert_path = os.path.join(domain_dir, CERT_NAME)
            key_path = os.path.join(domain_dir, KEY_NAME)
            ca_path = os.path.join(domain_dir, CA_NAME)
            with open(cert_path, 'w') as cert_file:
                cert_file.write(data.get('cert', ''))
            with open(key_path, 'w') as key_file:
                key_file.write(data.get('key', ''))
            with open(ca_path, 'w') as ca_file:
                ca_file.write(data.get('ca', ''))
            
            log_and_print(f"成功保存 {domain} 的证书, 秘钥和证书链到 {domain_dir}", 'info')
            
            # 更新版本记录
            cert_info['version'] = current_version
        else:
            log_and_print(f"{domain} 的证书版本未更新, 跳过下载", 'info')
    
    except hvac.exceptions.Forbidden as e:
        log_and_print(f"权限错误: 无法访问 Vault 路径 {mount_point}/{path}. 错误信息: {e}", 'error')
    except hvac.exceptions.InvalidRequest as e:
        log_and_print(f"请求错误: 无效的请求 {mount_point}/{path}. 错误信息: {e}", 'error')
    except Exception as e:
        log_and_print(f"从 Vault 获取和保存证书数据时出错: {e}", 'error')
    
    return cert_info

def main():
    """主函数"""
    # 设置 Vault 客户端
    vault_client = setup_vault_client()
    
    while True:
        # 读取证书列表及其版本
        cert_list = read_cert_list(VAULT_PATHS_FILE)
        updated_cert_list = {}
        
        for domain, info in cert_list.items():
            mount_point = info.get('mount', 'ssl')  # 默认挂载点为 'ssl'
            path = info.get('path', '')
            updated_cert_info = fetch_and_save_certificates(vault_client, domain, mount_point, path, info)
            
            if updated_cert_info:
                updated_cert_list[domain] = updated_cert_info
        
        # 写入更新后的版本信息
        write_cert_list(VAULT_PATHS_FILE, updated_cert_list)
        
        # 等待指定的时间间隔
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
