import subprocess
import sys
import hvac
import json
import time
from dateutil import parser
from dotenv import load_dotenv


# .env PATH 
dotenv_path = './.env'
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f".env loaded")
else:
    print(f"Err for .env loading")
    sys.exit(1)

# get Server env
# Vault' URL and Token
VAULT_URL = os.getenv('VAULT_URL')
VAULT_TOKEN = os.getenv('VAULT_TOKEN')
VAULT_PATHS_FILE = os.getenv('VAULT_PATHS_FILE', './vault_paths.json')
TOKEN_RENEWAL_THRESHOLD = int(os.getenv('TOKEN_RENEWAL_THRESHOLD', '604800'))  #  Renewal Time, remaining less than 7 days (unit: second) 
# path of the unseal key file
UNSEAL_KEYS_FILE = os.getenv('UNSEAL_KEYS_FILE', './vault_unseal_keys.json')
UNSEAL_LOGS_FILE = os.getenv('UNSEAL_LOGS_FILE', './vault_unseal.log')
# default path of ssl push to Vault 
DEFAULT_VAULT_PATH = os.getenv('DEFAULT_VAULT_PATH', 'ssl/data/default')

def install_dependencies():
    """auto install dependencies"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "hvac"])
        print("hvac installed")
    except subprocess.CalledProcessError as e:
        print(f"Err for install hvac: {e}")
        sys.exit(1)

# install dependencies
# install_dependencies()

# create Vault client
client = hvac.Client(
    url=VAULT_URL,
    token=VAULT_TOKEN
)

def read_cert_key_ca(cert_path, key_path, ca_path):
    """Load cert, key and chain form local file"""
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
        print(f"Err for load cert, key and chain: {e}")
        sys.exit(1)

def get_vault_path(domain):
    """Obtain the Vault path from the path mapping table. Return the default If the domain name is not in the list"""
    try:
        with open(VAULT_PATHS_FILE, 'r') as file:
            paths = json.load(file)
        # Gets the Vault path of the specified domain name. Use default path If it is not found 
        return paths.get(domain, DEFAULT_VAULT_PATH)
    except Exception as e:
        print(f"An error occurred load the path mapping table: {e}")
        # Use default path when error loading the path mapping table
        return DEFAULT_VAULT_PATH

def write_to_vault(vault_path, cert, key, ca, is_ecc):
    """save cert, key and Chian Vault"""
    if not vault_path:
        print("Vault path not defined")
        return

    try:
        # Process path format 
        mount_point, path = vault_path.split('/', 1)
        path = path.lstrip('/')  # Remove the slash at the beginning of the path 

        # upload cert, key, Chian and is_ecc Vault 
        client.secrets.kv.v2.create_or_update_secret(
            mount_point=mount_point,
            path=path,
            secret=dict(cert=cert, key=key, ca=ca, is_ecc=is_ecc)
        )
        print(f"uploaded: {vault_path}")
    except Exception as e:
        print(f"Err when upload cert, key, Chian and is_ecc Vault: {e}")

def renew_token_if_needed():
    """Check whether the token is nearing expiration and renew"""
    try:
        # lookup token 
        token_info = client.lookup_token()
        expire_time = token_info['data']['expire_time']
        current_time = time.time()
        
        # check expire_time
        expire_time_dt = parser.parse(expire_time)
        expire_time_seconds = time.mktime(expire_time_dt.timetuple())
        ttl = expire_time_seconds - current_time

        # Renew the token If the remaining time is less than the threshold 
        if ttl < TOKEN_RENEWAL_THRESHOLD:
            if token_info['data'].get('renewable'):
                # client.auth.token.renew_token(token=VAULT_TOKEN,increment=3600*24*32) # renew specific Token 
                client.auth.token.renew_self(increment=3600*24*32) # renew self 
                print("Token Renewed")
            else:
                print("Token cannot renew")
        else:
            print("Token is valid enough, not need renew")
    except Exception as e:
        print(f"Error checking or renewing token: {e}")

def log_message(message):
    """save log to console and log file"""
    with open(UNSEAL_LOGS_FILE, 'a') as log_file:
        log_file.write(f"{message}\n")
    print(message)

def unseal_vault():
    """Unseal Vault"""
    try:
        with open(UNSEAL_KEYS_FILE, 'r') as file:
            unseal_keys = json.load(file)
        
        # load keys and unseal Vault 
        client.sys.submit_unseal_keys(unseal_keys)
        print("success to use keys")
        
        # check Vault seal status 
        if client.sys.is_sealed():
            print("Vault is still sealed")
        else:
            print("Vault unsealed")
    except Exception as e:
        print(f"Err for unseal Vault: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("method: upload_to_vault.py <cert_file> <key_file> <domain> <is_ecc> [<ca_file>]")
        sys.exit(1)

    cert_file_path = sys.argv[1]
    key_file_path = sys.argv[2]
    domain = sys.argv[3]
    is_ecc = sys.argv[4].lower() in ["true", "yes", "1", "--ecc", "-ecc"]
    ca_file_path = sys.argv[5] if len(sys.argv) == 6 else None

    # check Vault seal status
    if client.sys.is_sealed():
        log_message("Vault is sealed, try to unseal")
        unseal_vault()  # unseal Vault
    renew_token_if_needed()  # check and renew token 
    cert, key, ca = read_cert_key_ca(cert_file_path, key_file_path, ca_file_path)
    write_to_vault(get_vault_path(domain), cert, key, ca, is_ecc)

