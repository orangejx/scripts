import os
import json
import shutil
import sys
from datetime import datetime

# 配置文件路径
CONFIG_FILE = '/acme.sh/account.conf'
JSON_FILE = './acme-dns_list.json'
profile_path = '~/.profile'

def read_config():
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    config[key] = value
    return config

def write_config(config, updated_keys):
    temp_file = CONFIG_FILE + '.tmp'
    with open(temp_file, 'w') as f:
        for line in open(CONFIG_FILE, 'r'):
            if '=' in line:
                key, _ = line.strip().split('=', 1)
                if key not in updated_keys:
                    f.write(line)

        for key in updated_keys:
            if key in config:
                value = config[key]
                # 加上单引号
                if not (value.startswith("'") and value.endswith("'")):
                    value = f"'{value}'"
                f.write(f"{key}={value}\n")

    # 替换原文件
    shutil.move(temp_file, CONFIG_FILE)

def backup_config():
    timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    backup_file = f"{CONFIG_FILE}-{timestamp}.bak"
    shutil.copy(CONFIG_FILE, backup_file)

def update_profile(config):
    profile_file = os.path.expanduser(profile_path)
    profile_config = {
        'ACMEDNS_USERNAME': config.get('SAVED_ACMEDNS_USERNAME', ''),
        'ACMEDNS_PASSWORD': config.get('SAVED_ACMEDNS_PASSWORD', ''),
        'ACMEDNS_BASE_URL': config.get('SAVED_ACMEDNS_BASE_URL', ''),
        'ACMEDNS_SUBDOMAIN': config.get('SAVED_ACMEDNS_SUBDOMAIN', '')
    }

    # Read current .profile if it exists
    existing_profile_config = {}
    if os.path.exists(profile_file):
        with open(profile_file, 'r') as f:
            for line in f:
                if line.startswith('export '):
                    key_value = line[len('export '):].strip()
                    if '=' in key_value:
                        key, value = key_value.split('=', 1)
                        existing_profile_config[key] = value.strip("'")

    with open(profile_file, 'w') as f:
        for key, value in profile_config.items():
            # 加上单引号
            if not (value.startswith("'") and value.endswith("'")):
                value = f"'{value}'"
            if value != existing_profile_config.get(key, ''):
                f.write(f"export {key}={value}\n")

def main():
    # 检查参数
    if len(sys.argv) != 2:
        print("Usage: python script.py <domain>")
        sys.exit(1)

    domain = sys.argv[1]

    # 读取 JSON 文件
    with open(JSON_FILE) as f:
        dns_config = json.load(f)

    # 读取现有配置
    current_config = read_config()

    # 新配置字典
    updated_keys = ['SAVED_ACMEDNS_USERNAME', 'SAVED_ACMEDNS_PASSWORD', 'SAVED_ACMEDNS_BASE_URL', 'SAVED_ACMEDNS_SUBDOMAIN']
    new_config = {key: dns_config.get(domain, {}).get(key.split('_')[-1].lower(), '') for key in updated_keys}

    ## 如果配置有变化
    #if any(current_config.get(key) != new_config[key] for key in updated_keys):
    #    # 备份配置文件
    #    backup_config()
    #    # 写入配置文件
    #    write_config(new_config, updated_keys)

    # 更新 ~/.profile
    update_profile(new_config)

    print("acme-dns 配置信息加载完成. ")
    # # 延时 10 秒
    # import time
    # time.sleep(5)

if __name__ == '__main__':
    main()
