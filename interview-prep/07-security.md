# 🔐 Security

---

## 1. Principle of Least Privilege là gì?

**Principle of Least Privilege (PoLP):** Mỗi user, service, hay process chỉ được cấp **quyền tối thiểu** cần thiết để thực hiện công việc của mình.

**Ví dụ thực tế:**

```
❌ Sai: EC2 App Server có FullAdminAccess
✅ Đúng: EC2 App Server chỉ có:
   - s3:GetObject, s3:PutObject → notemesh-uploads bucket
   - secretsmanager:GetSecretValue → /notemesh/prod/* 
   - rds-db:connect → notemesh database

❌ Sai: Jenkins có AWS AdministratorAccess
✅ Đúng: Jenkins chỉ có:
   - ecr:PushImage, ecr:GetAuthorizationToken
   - ecs:UpdateService (hoặc ansible qua SSH không cần AWS creds)
```

**Áp dụng trong các tầng:**
- **AWS IAM:** Tạo role riêng cho từng service với policy tối thiểu
- **Database:** App user chỉ có `SELECT, INSERT, UPDATE, DELETE`, không có `DROP TABLE`
- **Linux:** Run service với non-root user, không dùng sudo không cần thiết
- **Network:** Security Group chỉ mở port cần thiết, đúng source

---

## 2. Tại sao không nên dùng root account trên AWS?

**Root account** là tài khoản email đăng ký AWS, có **full quyền tuyệt đối** với toàn bộ AWS account, **không thể restrict**.

**Rủi ro:**
- Bị hack → mất toàn bộ resources, data, billing
- Vô tình xóa resources critical
- Access keys bị leak → thảm họa

**Best practices:**

```
1. Enable MFA (Multi-Factor Authentication) ngay lập tức
2. Không tạo Access Keys cho root account
3. Tạo IAM Admin user/group cho công việc hàng ngày
4. Lock root credentials đi, chỉ dùng cho:
   - Thay đổi account settings
   - Đóng account
   - Restore bị khóa

5. Bật AWS Organizations + Service Control Policies (SCP)
   để giới hạn root ở member accounts
```

---

## 3. Secret Management - làm sao tránh hardcode credentials?

**❌ Anti-patterns:**
```bash
# Hardcode trong code
DB_PASSWORD="Super$ecret123"

# Trong Dockerfile
ENV API_KEY=abc123xyz

# Trong docker-compose.yml commit lên git
environment:
  - DATABASE_URL=postgresql://admin:password@db:5432/app
```

**✅ Best practices:**

**1. Environment Variables (cơ bản nhất):**
```bash
# .env file (thêm vào .gitignore)
DATABASE_URL=postgresql://admin:password@db:5432/app

# Load trong Docker Compose
env_file:
  - .env
```

**2. AWS Secrets Manager (production):**
```python
import boto3
import json

client = boto3.client('secretsmanager', region_name='ap-southeast-1')
secret = client.get_secret_value(SecretId='notemesh/prod/db-credentials')
creds = json.loads(secret['SecretString'])

DB_PASSWORD = creds['password']
```

**3. AWS SSM Parameter Store (đơn giản hơn):**
```bash
# Lưu secret
aws ssm put-parameter \
  --name "/notemesh/prod/db-password" \
  --value "SuperSecret123" \
  --type "SecureString"

# Đọc trong code
aws ssm get-parameter --name "/notemesh/prod/db-password" --with-decryption
```

**4. Vault (HashiCorp):** Cho môi trường on-prem hoặc multi-cloud.

**5. GitHub Secrets / CI/CD secrets:** Cho pipeline credentials.

**Key rules:**
- **Never commit** secrets vào git (dùng `git-secrets`, `pre-commit hooks`)
- **Rotate** credentials định kỳ
- **Audit** ai access secret và khi nào

---

## 4. SSL/TLS Certificate là gì? ACM dùng làm gì?

**SSL/TLS Certificate** là digital certificate xác thực danh tính của server và enable HTTPS.

**Nội dung certificate:**
- Domain name (Common Name / SAN)
- Public key
- Chữ ký số của CA (Certificate Authority)
- Ngày hết hạn

**Chain of Trust:**
```
Root CA (Mozilla, Google, Comodo...) [Trusted by browsers]
  └── Intermediate CA
        └── Your Certificate (notemesh.com)
```

**ACM (AWS Certificate Manager):**
- Cấp và quản lý SSL/TLS certificates **miễn phí** cho AWS resources
- **Tự động gia hạn** (không lo expiry)
- Tích hợp với **ALB, CloudFront, API Gateway** (không thể tải về install thủ công)
- Xác thực domain qua **DNS validation** (thêm CNAME record) hoặc **Email validation**

```
Workflow với ACM trong NoteMesh:
1. Request certificate cho *.notemesh.com trong ACM
2. Add CNAME record vào Hostinger DNS (DNS validation)
3. ACM issue certificate sau vài phút
4. Gắn certificate vào ALB (HTTPS listener)
5. ALB dùng cert để terminate SSL, forward HTTP nội bộ
```

---

## 5. SSH Key Pair hoạt động như thế nào?

**SSH (Secure Shell)** dùng **Asymmetric Cryptography** để authenticate.

**Cặp key:**
- **Private Key** (`~/.ssh/id_rsa` hoặc `notemesh.pem`): Bí mật, chỉ bạn có
- **Public Key** (`~/.ssh/id_rsa.pub`): Chia sẻ với server

**Quá trình kết nối:**
```
1. Client gửi request kết nối đến Server
2. Server gửi một "challenge" (random data)
3. Client ký challenge bằng Private Key → signature
4. Client gửi signature lên Server
5. Server dùng Public Key để verify signature
6. Verify thành công → cho phép kết nối
```

**File `~/.ssh/authorized_keys`** trên server: Chứa public keys của tất cả ai được phép kết nối.

**Thực tế với AWS EC2:**
```bash
# Tạo key pair trên AWS (private key tải về 1 lần duy nhất)
aws ec2 create-key-pair --key-name notemesh-key --query 'KeyMaterial' --output text > notemesh.pem
chmod 400 notemesh.pem

# SSH vào EC2
ssh -i notemesh.pem ubuntu@54.123.45.67

# Ansible dùng key pair
ansible_ssh_private_key_file = ~/.ssh/notemesh.pem
```

**Best practices:**
- **Không share** private key
- Dùng **passphrase** bảo vệ private key
- Mỗi môi trường/project có **key pair riêng**
- Thay key định kỳ
- Dùng **Bastion Host / Jump Server** thay vì expose SSH trực tiếp
