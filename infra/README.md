# NoteMesh Infrastructure

Hạ tầng AWS cho NoteMesh — Phương án 1 (Starter + Jenkins + ALB)

## Kiến trúc

```
notemesh.catcosy.shop  → CloudFront → S3 (Next.js static)
api.catcosy.shop       → ALB → EC2 App (FastAPI :8000)
jenkins.catcosy.shop   → ALB → EC2 Jenkins (:8080)
```

## Cấu trúc thư mục

```
infra/
├── terraform/          # Infrastructure as Code
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── providers.tf
│   ├── terraform.tfvars.example
│   └── modules/
│       ├── vpc/
│       ├── security_groups/
│       ├── acm/
│       ├── ec2/
│       ├── alb/
│       ├── rds/
│       ├── s3/
│       └── cloudfront/
├── ansible/            # Configuration Management
│   ├── inventory/
│   │   └── hosts.ini
│   ├── group_vars/
│   │   ├── all.yml
│   │   └── app_servers.yml
│   ├── roles/
│   │   ├── common/
│   │   ├── docker/
│   │   ├── app_server/
│   │   └── jenkins/
│   ├── playbooks/
│   │   └── deploy_app.yml
│   └── site.yml
└── scripts/
    ├── user_data_app.sh
    └── user_data_jenkins.sh
```

## Điều kiện tiên quyết

```bash
# Cài công cụ cần thiết
brew install terraform ansible awscli   # macOS
# hoặc
sudo apt-get install -y terraform ansible awscli  # Ubuntu

# Cấu hình AWS credentials
aws configure
# AWS Access Key ID: ...
# AWS Secret Access Key: ...
# Default region: ap-southeast-1
```

## Quy trình triển khai

### Bước 1 — Tạo EC2 Key Pair

```bash
# Tạo key pair trên AWS Console → EC2 → Key Pairs
# hoặc dùng CLI:
aws ec2 create-key-pair \
  --key-name notemesh-keypair \
  --query 'KeyMaterial' \
  --output text > ~/.ssh/notemesh-keypair.pem
chmod 400 ~/.ssh/notemesh-keypair.pem
```

### Bước 2 — Cấu hình Terraform

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Điền các giá trị thực vào terraform.tfvars

# Lấy IP của bạn:
curl ifconfig.me
```

### Bước 3 — Terraform Init & Apply

```bash
cd infra/terraform
terraform init
terraform plan    # Xem preview
terraform apply   # Tạo tất cả resource (~15-20 phút do RDS)
```

### Bước 4 — Lấy outputs và cấu hình Hostinger DNS

```bash
terraform output
# Sẽ hiển thị:
# alb_dns_name                = "notemesh-prod-alb-xxx.ap-southeast-1.elb.amazonaws.com"
# cloudfront_domain           = "d1234abcd.cloudfront.net"
# acm_alb_validation_records  = { ... }
# acm_cloudfront_validation_records = { ... }
```

**Thêm vào Hostinger DNS Manager:**
```
notemesh.catcosy.shop  CNAME  → d1234abcd.cloudfront.net
api.catcosy.shop       CNAME  → notemesh-prod-alb-xxx.ap-southeast-1.elb.amazonaws.com
jenkins.catcosy.shop   CNAME  → notemesh-prod-alb-xxx.ap-southeast-1.elb.amazonaws.com

# + Thêm các ACM validation CNAME (từ output acm_*_validation_records)
```

### Bước 5 — Cấu hình Ansible

```bash
# Điền IP vào inventory
cd infra/ansible
nano inventory/hosts.ini
# Điền APP_SERVER_PUBLIC_IP và JENKINS_SERVER_PUBLIC_IP từ terraform output

# Điền thông tin database và secrets
nano group_vars/app_servers.yml
```

### Bước 6 — Chạy Ansible

```bash
# Test kết nối SSH
ansible all -i inventory/hosts.ini -m ping

# Setup toàn bộ (app + jenkins)
ansible-playbook -i inventory/hosts.ini site.yml

# Deploy chỉ app (sau khi infrastructure đã cấu hình)
ansible-playbook -i inventory/hosts.ini playbooks/deploy_app.yml
```

### Bước 7 — Verify

```bash
# Kiểm tra API
curl https://api.catcosy.shop/health

# Kiểm tra Jenkins
open https://jenkins.catcosy.shop

# Kiểm tra web
open https://notemesh.catcosy.shop
```

## Bảo mật — Lưu ý quan trọng

```bash
# Mã hóa secrets với ansible-vault
ansible-vault encrypt_string 'YOUR_DB_PASSWORD' --name 'db_password'
# Chạy playbook với vault
ansible-playbook site.yml --ask-vault-pass
```

- **Không commit** `terraform.tfvars` vào git (đã có trong .gitignore)
- **Không commit** file `.pem` key pair
- Dùng `ansible-vault` để mã hóa secrets trong `group_vars/`
- Sau production ổn định: bật `deletion_protection = true` trên RDS

## Destroy Infrastructure

```bash
cd infra/terraform
terraform destroy
```
