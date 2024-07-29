import subprocess
import sys
import hvac
import json
import time
from dateutil import parser
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
VAULT_PATHS_FILE = os.getenv('VAULT_PATHS_FILE', '/scripts/vault_paths.json')
TOKEN_RENEWAL_THRESHOLD = int(os.getenv('TOKEN_RENEWAL_THRESHOLD', '604800'))  # Token 剩余时间低于 7 天时续期（单位：秒）
# 解封密钥文件路径
UNSEAL_KEYS_FILE = os.getenv('UNSEAL_KEYS_FILE', '/scripts/vault_unseal_keys.json')
UNSEAL_LOGS_FILE = os.getenv('UNSEAL_LOGS_FILE', '/scripts/vault_unseal.log')
# 默认 Vault 路径
DEFAULT_VAULT_PATH = os.getenv('DEFAULT_VAULT_PATH', 'ssl/data/default')

def install_dependencies():
    """自动安装依赖"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "hvac"])
        print("依赖库 hvac 已成功安装")
    except subprocess.CalledProcessError as e:
        print(f"安装依赖库时出错: {e}")
        sys.exit(1)

# 安装依赖库
# install_dependencies()

# 创建 Vault 客户端
client = hvac.Client(
    url=VAULT_URL,
    token=VAULT_TOKEN
)

def read_cert_key_ca(cert_path, key_path, ca_path):
    """从本地文件读取证书、密钥和 CA"""
    try:
        with open(cert_path, 'r') as cert_file:
            cert = cert_file.read()
        with open(key_path, 'r') as key_file:
            key = key_file.read()
        ca = ""
        if ca_path:
            with open(ca_path, 'r') as ca_file:
                ca = ca_file.read()
        return cert, key, ca
    except Exception as e:
        print(f"读取证书、密钥或 CA 文件时出错: {e}")
        sys.exit(1)

def get_vault_path(domain):
    """从路径映射表中获取 Vault 路径，如果域名不在列表中，返回默认路径"""
    try:
        with open(VAULT_PATHS_FILE, 'r') as file:
            paths = json.load(file)
        # 获取指定域名的 Vault 路径，如果没有找到，则使用默认路径
        return paths.get(domain, DEFAULT_VAULT_PATH)
    except Exception as e:
        print(f"读取路径映射表时出错: {e}")
        # 在读取路径映射表出错时也使用默认路径
        return DEFAULT_VAULT_PATH

def write_to_vault(vault_path, cert, key, ca, is_ecc):
    """将证书、密钥和 CA 写入 Vault"""
    if not vault_path:
        print("Vault 路径未定义")
        return

    try:
        # 处理路径格式
        mount_point, path = vault_path.split('/', 1)
        path = path.lstrip('/')  # 去掉路径开头的斜杠

        # 上传证书、密钥、CA 和是否为 ECC 到 Vault
        client.secrets.kv.v2.create_or_update_secret(
            mount_point=mount_point,
            path=path,
            secret=dict(cert=cert, key=key, ca=ca, is_ecc=is_ecc)
        )
        print(f"成功将证书、密钥、CA 和是否为 ECC 写入 Vault 路径: {vault_path}")
    except Exception as e:
        print(f"将证书、密钥、CA 和是否为 ECC 写入 Vault 时出错: {e}")

def renew_token_if_needed():
    """检查 token 是否接近过期并续期"""
    try:
        # 获取当前 token 的信息
        token_info = client.lookup_token()
        expire_time = token_info['data']['expire_time']
        current_time = time.time()
        
        # 解析 expire_time
        expire_time_dt = parser.parse(expire_time)
        expire_time_seconds = time.mktime(expire_time_dt.timetuple())
        ttl = expire_time_seconds - current_time

        # 如果剩余时间小于阈值，则续期 token
        if ttl < TOKEN_RENEWAL_THRESHOLD:
            if token_info['data'].get('renewable'):
                client.renew_token()
                print("Token 已续期")
            else:
                print("Token 不可续期")
        else:
            print("Token 有效期足够，无需续期")
    except Exception as e:
        print(f"检查或续期 token 时出错: {e}")

def log_message(message):
    """记录日志到控制台和文件"""
    with open(UNSEAL_LOGS_FILE, 'a') as log_file:
        log_file.write(f"{message}\n")
    print(message)

def unseal_vault():
    """解封 Vault"""
    try:
        with open(UNSEAL_KEYS_FILE, 'r') as file:
            unseal_keys = json.load(file)
        
        # 解封密钥并解封 Vault 
        client.sys.submit_unseal_keys(unseal_keys)
        print("使用解密密钥成功")
        
        # 检查 Vault 是否已解封
        if client.sys.is_sealed():
            print("Vault 仍然是封闭的")
        else:
            print("Vault 已成功解封")
    except Exception as e:
        print(f"解封 Vault 时出错: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("使用方法: upload_to_vault.py <cert_file> <key_file> <domain> <is_ecc> [<ca_file>]")
        sys.exit(1)

    cert_file_path = sys.argv[1]
    key_file_path = sys.argv[2]
    domain = sys.argv[3]
    is_ecc = sys.argv[4].lower() in ["true", "yes", "1", "--ecc", "-ecc"]
    ca_file_path = sys.argv[5] if len(sys.argv) == 6 else None

    # 检查 Vault 是否被封印
    if client.sys.is_sealed():
        log_message("Vault 被封印, 开始解封")
        unseal_vault()  # 解封 Vault
    renew_token_if_needed()  # 检查并续期 token
    cert, key, ca = read_cert_key_ca(cert_file_path, key_file_path, ca_file_path)
    write_to_vault(get_vault_path(domain), cert, key, ca, is_ecc)

