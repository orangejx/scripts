import hvac
import json
import os
import sys
import time
import logging
from dotenv import load_dotenv
from dateutil.parser import parse


# .env PATH 
dotenv_path = './.env'
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f".env loaded")
else:
    print(f"Error loading the .env")
    sys.exit(1)

# load env configuration 
# Vault URL and Token
VAULT_URL = os.getenv('VAULT_URL')
VAULT_TOKEN = os.getenv('VAULT_TOKEN')
VAULT_PATHS_FILE = os.getenv('VAULT_PATHS_FILE', './vault_paths.json')
UNSEAL_KEYS_FILE = os.getenv('UNSEAL_KEYS_FILE', './vault_unseal_keys.json')
UNSEAL_LOGS_FILE = os.getenv('UNSEAL_LOGS_FILE', './vault_unseal.log')
OUTPUT_DIR = os.getenv('OUTPUT_DIR', './ssl')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '604800'))  # default: 1 week 
TOKEN_RENEWAL_THRESHOLD = int(os.getenv('TOKEN_RENEWAL_THRESHOLD', '604800'))  #  Renewal Time,
LOG_FILE = os.getenv('LOG_FILE', './update.log')
CERT_NAME = os.getenv('CERT_NAME', 'fullchain.pem')
KEY_NAME = os.getenv('KEY_NAME', 'privkey.pem')
CA_NAME = os.getenv('CA_NAME', 'ca.pem')

# config log 
logging.basicConfig(filename=LOG_FILE,
                    level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def log_and_print(message, level='info'):
    """
    save log and print it to console
    """
    # print it to console 
    print(message)
    
    # log made based on the log level
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
    """Loading Cert List and version"""
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        log_and_print(f"Error loading cert list: {e}", 'error')
        return {}

def write_cert_list(file_path, data):
    """save updated cert config info and version to JSON file"""
    try:
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        log_and_print(f"Error save cert list: {e}", 'error')

def setup_vault_client():
    """set Vault client"""
    return hvac.Client(url=VAULT_URL, token=VAULT_TOKEN)

def get_local_version(cert_info):
    """Load version from local cert info"""
    version_str = cert_info.get('version', '')
    try:
        return int(version_str)
    except ValueError:
        return None

def fetch_and_save_certificates(vault_client, domain, mount_point, path, cert_info):
    """save Cert, Key and Chian from Vault"""
    try:
        local_version = get_local_version(cert_info)
        vault_params = {
            "mount_point": mount_point,
            "path": path
        }
        fetch_latest = True
        
        if local_version is not None:
            # get current version from Vault
            secret_metadata = vault_client.secrets.kv.v2.read_secret_metadata(**vault_params)
            current_version = secret_metadata['data']['current_version']
            if current_version == local_version:
                fetch_latest = False
            else:
                # set version need to update
                vault_params['version'] = current_version
                
        
        vault_params["raise_on_deleted_version"] = True  # Avoid errors in accessing deleted versions 
        if fetch_latest:
            # get current version data from Vault 
            secret = vault_client.secrets.kv.v2.read_secret_version(**vault_params)
            data = secret['data']['data']
            current_version = secret['data']['metadata']['version']
            
            # create domain dir
            domain_dir = os.path.join(OUTPUT_DIR, domain)
            os.makedirs(domain_dir, exist_ok=True)
            
            # save Cert, Key and Chain to file 
            cert_path = os.path.join(domain_dir, CERT_NAME)
            key_path = os.path.join(domain_dir, KEY_NAME)
            ca_path = os.path.join(domain_dir, CA_NAME)
            with open(cert_path, 'w') as cert_file:
                cert_file.write(data.get('cert', ''))
            with open(key_path, 'w') as key_file:
                key_file.write(data.get('key', ''))
            with open(ca_path, 'w') as ca_file:
                ca_file.write(data.get('ca', ''))
            
            log_and_print(f"success get cert, key and chain for {domain}, and save to {domain_dir}", 'info')
            
            # update version for local 
            cert_info['version'] = current_version
        else:
            log_and_print(f"{domain}'s cert is up to date, Skipped", 'info')
    
    except hvac.exceptions.Forbidden as e:
        log_and_print(f"Permission Denied: cannot get Vault path {mount_point}/{path}. Err: {e}", 'error')
    except hvac.exceptions.InvalidRequest as e:
        log_and_print(f"Wrong request: invalid request {mount_point}/{path}. Err: {e}", 'error')
    except Exception as e:
        log_and_print(f"Wrong obtaining and saving cert data from Vault: {e}", 'error')
    
    return cert_info


def renew_token_if_needed(vault_client):
    """Check whether the token is nearing expiration and renew"""
    try:
        # lookup token 
        token_info = vault_client.lookup_token()
        expire_time = token_info['data']['expire_time']
        current_time = time.time()
        
        # check expire_time
        expire_time_dt = parse(expire_time)
        expire_time_seconds = time.mktime(expire_time_dt.timetuple())
        ttl = expire_time_seconds - current_time

        # Renew the token If the remaining time is less than the threshold 
        if ttl < TOKEN_RENEWAL_THRESHOLD:
            if token_info['data'].get('renewable'):
                vault_client.renew_token()
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


def unseal_vault(vault_client):
    """Unseal Vault"""
    try:
        with open(UNSEAL_KEYS_FILE, 'r') as file:
            unseal_keys = json.load(file)
        
        # load keys and unseal Vault 
        vault_client.sys.submit_unseal_keys(unseal_keys)
        print("success to use keys")
        
        # check Vault seal status 
        if vault_client.sys.is_sealed():
            print("Vault is still sealed")
        else:
            print("Vault unsealed")
    except Exception as e:
        print(f"Err for unseal Vault: {e}")


def main():
    """main function"""
    # set Vault client
    vault_client = setup_vault_client()
    
    # while True: # line: 206~229 
    
    # get cert list and version 
    cert_list = read_cert_list(VAULT_PATHS_FILE)
    updated_cert_list = {}
    
    # check Vault seal status
    if vault_client.sys.is_sealed():
        log_message("Vault is sealed, try to unseal")
        unseal_vault(vault_client)  # unseal Vault
    
    renew_token_if_needed(vault_client)  # check and renew token 
    
    for domain, info in cert_list.items():
        mount_point = info.get('mount', 'ssl')  # default mount point is 'ssl'
        path = info.get('path', '')
        updated_cert_info = fetch_and_save_certificates(vault_client, domain, mount_point, path, info)
        
        if updated_cert_info:
            updated_cert_list[domain] = updated_cert_info
    
    # save new version info updated
    write_cert_list(VAULT_PATHS_FILE, updated_cert_list)
    
    # # scheduled restart task
    # time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()

