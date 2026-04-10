#!/bin/bash
# user_data_app.sh — Bootstrap EC2 App Server
# Chạy 1 lần khi EC2 khởi động lần đầu
set -euo pipefail

LOG="/var/log/user_data.log"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date)] === Starting App Server Bootstrap ==="

# ── Cập nhật hệ thống ─────────────────────────────────────────────────────────
apt-get update -y
apt-get upgrade -y
apt-get install -y curl git unzip jq awscli

# ── Swap 2GB (t3.medium có sẵn 4GB RAM nhưng thêm swap cho an toàn) ──────────
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# ── Cài Docker Engine ─────────────────────────────────────────────────────────
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker
usermod -aG docker ubuntu

# ── Cài Docker Compose v2 ─────────────────────────────────────────────────────
COMPOSE_VERSION="v2.27.0"
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# ── Tạo thư mục app ───────────────────────────────────────────────────────────
mkdir -p /opt/notemesh
chown ubuntu:ubuntu /opt/notemesh

echo "[$(date)] === App Server Bootstrap Complete ==="
echo "[$(date)] Run Ansible playbook to deploy the app"
