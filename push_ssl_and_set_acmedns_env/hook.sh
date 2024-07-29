#!/bin/sh

# set log file path 
LOG_FILE="/scripts/acme_hook.log"

# function for logging 
log_message() {
    local message="$1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $message" >> "$LOG_FILE"
}

# check args 
if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <domain> <is_ecc>"
  log_message "Err: Missing args"
  exit 1
fi

DOMAIN=$1
IS_ECC=$2

# create temp dir 
TEMP_DIR="/tmp"
DOMAIN_DIR="$TEMP_DIR/$DOMAIN"
# temp dir is exist? created if not 
if [ ! -d "$DOMAIN_DIR" ]; then
  echo "$DOMAIN_DIR creating..."
  mkdir -p "$DOMAIN_DIR"
  if [ $? -ne 0 ]; then
    echo "Err: cannot create $DOMAIN_DIR"
    log_message "Err: cannot create $DOMAIN_DIR"
    exit 1
  fi
  log_message "$DOMAIN_DIR created"
fi

# build cert path 
CERT_PATH="$DOMAIN_DIR/fullchain.pem"
KEY_PATH="$DOMAIN_DIR/privkey.pem"
CA_PATH="$DOMAIN_DIR/ca.pem"

# print temp dir path to debug
echo "Build cert path: $DOMAIN_DIR"
log_message "Build cert path: $DOMAIN_DIR"

# is ECC cert? 
if [ "$IS_ECC" = "true" ] || [ "$IS_ECC" = "yes" ] || [ "$IS_ECC" = "1" ] || [ "$IS_ECC" = "--ecc" ] || [ "$IS_ECC" = "-ecc" ]; then
  acme.sh --install-cert -d "$DOMAIN" --ecc \
    --fullchain-file "$CERT_PATH" \
    --key-file "$KEY_PATH" \
    --ca-file "$CA_PATH"
else
  acme.sh --install-cert -d "$DOMAIN" \
    --fullchain-file "$CERT_PATH" \
    --key-file "$KEY_PATH" \
    --ca-file "$CA_PATH"
fi

# print temp dir path to debug
echo "Cert: $CERT_PATH"
echo "Key: $KEY_PATH"
echo "Chain: $CA_PATH"
log_message "Cert: $CERT_PATH"
log_message "Key: $KEY_PATH"
log_message "Chain: $CA_PATH"

# start to log
log_message "start to run script"

# save args
log_message "Domain: $DOMAIN"

# try to upload cert, key and chain to Vault Via python script 
log_message "try to upload cert, key and chain to Vault Via python script"
python3 /scripts/upload_to_vault.py "$CERT_PATH" "$KEY_PATH" "$DOMAIN" "$IS_ECC" "$CA_PATH"

# check python exit status 
if [ $? -eq 0 ]; then
    log_message "Cert uploaded"
else
    log_message "Err: failed to uplaod"
    exit 1
fi

#echo "temp dir $DOMAIN_DIR will delete after 5s" 
#sleep 5
#
## delete temp dir
#rm -rf "$DOMAIN_DIR"
#echo "temp dir $DOMAIN_DIR deleted" 
#log_message "temp dir $DOMAIN_DIR deleted"

# script completed
log_message "script completed"

