#!/bin/sh

# 设置日志文件路径
LOG_FILE="/scripts/acme_hook.log"

# 函数用于记录日志
log_message() {
    local message="$1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $message" >> "$LOG_FILE"
}

# 检查参数
if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <domain> <is_ecc>"
  log_message "错误: 参数不足"
  exit 1
fi

DOMAIN=$1
IS_ECC=$2

# 创建域名目录
TEMP_DIR="/tmp"
DOMAIN_DIR="$TEMP_DIR/$DOMAIN"
# 检查 /tmp 目录是否存在，如果不存在则创建
if [ ! -d "$DOMAIN_DIR" ]; then
  echo "$DOMAIN_DIR 目录不存在, 正在创建..."
  mkdir -p "$DOMAIN_DIR"
  if [ $? -ne 0 ]; then
    echo "错误: 无法创建 $DOMAIN_DIR 目录"
    log_message "错误: 无法创建 $DOMAIN_DIR 目录"
    exit 1
  fi
  log_message "$DOMAIN_DIR 目录已创建"
fi

# 构建证书路径 
CERT_PATH="$DOMAIN_DIR/fullchain.pem"
KEY_PATH="$DOMAIN_DIR/privkey.pem"
CA_PATH="$DOMAIN_DIR/ca.pem"

# 打印临时目录路径以便调试
echo "构建证书路径: $DOMAIN_DIR"
log_message "构建证书路径: $DOMAIN_DIR"

# 判断是否为 ECC 证书
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

# 打印证书路径以便调试
echo "证书: $CERT_PATH"
echo "秘钥: $KEY_PATH"
echo "C A : $CA_PATH"
log_message "证书路径: $CERT_PATH"
log_message "私钥路径: $KEY_PATH"
log_message "C A 路径: $CA_PATH"

# 记录开始日志
log_message "脚本开始执行"

# 记录参数信息
log_message "域名: $DOMAIN"

# 运行 Python 脚本以将证书和密钥上传到 Vault
log_message "运行 Python 脚本 /scripts/upload_to_vault.py"
python3 /scripts/upload_to_vault.py "$CERT_PATH" "$KEY_PATH" "$DOMAIN" "$IS_ECC" "$CA_PATH"

# 检查 Python 脚本的退出状态
if [ $? -eq 0 ]; then
    log_message "Python 脚本执行成功"
else
    log_message "错误: Python 脚本执行失败"
    exit 1
fi

#echo "临时目录 $DOMAIN_DIR 将在 5 秒后删除" 
#sleep 5
#
## 清理临时目录
#rm -rf "$DOMAIN_DIR"
#echo "临时目录 $DOMAIN_DIR 已删除" 
#log_message "临时目录 $DOMAIN_DIR 已删除"

# 记录脚本完成日志
log_message "脚本执行完成"

