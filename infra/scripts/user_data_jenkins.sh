#!/bin/bash
# user_data_jenkins.sh — Bootstrap EC2 Jenkins Server
set -euo pipefail

LOG="/var/log/user_data.log"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date)] === Starting Jenkins Server Bootstrap ==="

# ── Cập nhật hệ thống ─────────────────────────────────────────────────────────
apt-get update -y
apt-get upgrade -y
apt-get install -y curl git unzip jq awscli fontconfig

# ── Cài Java 21 (Jenkins yêu cầu Java 17+) ──────────────────────────────────
apt-get install -y openjdk-21-jdk

# ── Cài Jenkins LTS ───────────────────────────────────────────────────────────
curl -fsSL https://pkg.jenkins.io/debian-stable/jenkins.io-2023.key | \
  gpg --dearmor -o /usr/share/keyrings/jenkins-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/jenkins-keyring.gpg] \
  https://pkg.jenkins.io/debian-stable binary/" | \
  tee /etc/apt/sources.list.d/jenkins.list > /dev/null
apt-get update -y
apt-get install -y jenkins

systemctl enable jenkins
systemctl start jenkins

# ── Cài Docker (Jenkins agents cần Docker để build image) ────────────────────
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker
usermod -aG docker jenkins
usermod -aG docker ubuntu

# ── Cài Docker Compose v2 ─────────────────────────────────────────────────────
COMPOSE_VERSION="v2.27.0"
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# ── Swap 2GB ─────────────────────────────────────────────────────────────────
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "[$(date)] === Jenkins Bootstrap Complete ==="
echo "[$(date)] Jenkins initial admin password:"
cat /var/lib/jenkins/secrets/initialAdminPassword 2>/dev/null || echo "(not yet available)"
