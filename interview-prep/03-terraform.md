# 🏗️ Infrastructure as Code - Terraform

---

## 1. Terraform là gì? Tại sao dùng IaC thay vì click tay trên console?

**Terraform** là công cụ IaC (Infrastructure as Code) của HashiCorp, dùng ngôn ngữ HCL (HashiCorp Configuration Language) để định nghĩa và quản lý infrastructure.

**Tại sao dùng IaC thay vì click tay:**

| | Click tay (ClickOps) | IaC (Terraform) |
|-|---------------------|-----------------|
| Tái tạo | Khó, dễ sai | Chạy lại 1 lệnh |
| Version control | Không thể | Git tracking đầy đủ |
| Review | Không thể | Code review như code thường |
| Audit | Khó | Git log rõ ràng |
| Multi-env | Copy-paste, dễ nhầm | Module tái sử dụng |
| Disaster recovery | Chậm, tốn thời gian | Recreate trong vài phút |

**Terraform vs CloudFormation:**
- Terraform: Multi-cloud (AWS, GCP, Azure, Kubernetes...)
- CloudFormation: AWS only, nhưng tích hợp sâu hơn với AWS

---

## 2. Giải thích luồng: terraform init → terraform plan → terraform apply

```
terraform init
├── Tải provider plugins (aws, google, kubernetes...)
├── Khởi tạo backend (S3, local...)
└── Tải modules

terraform plan
├── Đọc state file hiện tại
├── Đọc config HCL
├── So sánh desired state vs current state
└── Hiển thị diff: sẽ tạo gì, xóa gì, thay đổi gì (KHÔNG thay đổi thực tế)

terraform apply
├── Chạy plan một lần nữa
├── Hiển thị plan và hỏi confirm (yes/no)
├── Thực thi thay đổi trên cloud
└── Cập nhật state file
```

**Các lệnh khác quan trọng:**
```bash
terraform destroy          # Xóa tất cả resource trong state
terraform fmt              # Format code HCL
terraform validate         # Kiểm tra syntax
terraform output           # Xem output values
terraform state list       # Liệt kê resource trong state
terraform import           # Import resource đã tồn tại vào state
terraform taint            # Đánh dấu resource cần recreate
terraform refresh          # Sync state với thực tế
```

---

## 3. State file (terraform.tfstate) là gì? Tại sao cần lưu remote state?

**State file** là file JSON lưu toàn bộ thông tin về infrastructure mà Terraform đang quản lý. Đây là "source of truth" của Terraform.

```json
// terraform.tfstate (đơn giản hóa)
{
  "resources": [
    {
      "type": "aws_instance",
      "name": "app_server",
      "instances": [{
        "attributes": {
          "id": "i-0abc123",
          "instance_type": "t3.medium",
          "public_ip": "54.123.45.67"
        }
      }]
    }
  ]
}
```

**Vấn đề với local state:**
- Làm việc nhóm → mỗi người có state khác nhau → conflict
- Mất máy → mất state → Terraform không biết resource nào đang tồn tại
- Không an toàn (state chứa secrets như DB password)

**Remote State với S3 + DynamoDB:**
```hcl
# providers.tf
terraform {
  backend "s3" {
    bucket         = "my-terraform-state"
    key            = "notemesh/prod/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "terraform-locks"  # State locking
    encrypt        = true
  }
}
```

**DynamoDB State Locking:** Ngăn 2 người chạy `terraform apply` cùng lúc → tránh conflict state.

---

## 4. Module trong Terraform là gì? Lợi ích khi dùng module?

**Module** là tập hợp các resource Terraform được nhóm lại và tái sử dụng.

```
modules/
├── ec2/
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── rds/
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
└── s3/
    ├── main.tf
    ├── variables.tf
    └── outputs.tf
```

**Gọi module:**
```hcl
module "app_server" {
  source        = "./modules/ec2"
  instance_type = "t3.medium"
  ami_id        = "ami-0abcdef123456"
  subnet_id     = module.vpc.private_subnet_id
}
```

**Lợi ích:**
- **DRY (Don't Repeat Yourself):** Tạo 5 EC2 khác nhau chỉ cần gọi module 5 lần
- **Tái sử dụng:** Module EC2 dùng cho nhiều project
- **Abstraction:** Ẩn complexity, expose interface đơn giản
- **Versioning:** `source = "git::https://github.com/org/modules.git//ec2?ref=v1.2.0"`

---

## 5. `data` source vs `resource` khác nhau thế nào?

| | `resource` | `data` |
|-|------------|--------|
| Mục đích | **Tạo/quản lý** resource | **Đọc** resource đã tồn tại |
| Thay đổi | Terraform tạo, sửa, xóa | Chỉ đọc, không thay đổi |
| Ví dụ | Tạo EC2 mới | Đọc AMI ID mới nhất |

```hcl
# resource: Tạo mới
resource "aws_instance" "app" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.medium"
}

# data: Đọc AMI Ubuntu mới nhất (không tạo gì)
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-*"]
  }
}

# data: Đọc thông tin VPC đã tạo sẵn
data "aws_vpc" "existing" {
  tags = { Name = "production-vpc" }
}
```

---

## 6. `depends_on` dùng để làm gì?

Terraform tự động nhận biết dependency thông qua **reference** (implicit dependency).

```hcl
# Implicit dependency: EC2 reference đến SG → Terraform biết tạo SG trước
resource "aws_instance" "app" {
  security_groups = [aws_security_group.app.id]  # implicit dep
}
```

**`depends_on`** dùng khi có dependency nhưng không qua reference (explicit dependency):

```hcl
resource "aws_s3_bucket_policy" "app" {
  bucket = aws_s3_bucket.app.id
  policy = data.aws_iam_policy_document.app.json

  # S3 bucket policy cần IAM role tồn tại trước
  # nhưng không có reference trực tiếp
  depends_on = [aws_iam_role.app_role]
}
```

**Khi nào cần `depends_on`:**
- Resource A phụ thuộc vào side effect của Resource B (không phải output)
- Provisioner cần một service khác phải ready trước

---

## 7. Variables, Outputs, Locals trong Terraform - phân biệt

**Variables (Input):** Tham số đầu vào, có thể override từ bên ngoài

```hcl
# variables.tf
variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.medium"
  
  validation {
    condition     = contains(["t3.medium", "t3.large"], var.instance_type)
    error_message = "Must be t3.medium or t3.large."
  }
}

# Sử dụng
resource "aws_instance" "app" {
  instance_type = var.instance_type
}
```

**Outputs (Export):** Xuất giá trị để dùng ở nơi khác hoặc hiển thị

```hcl
# outputs.tf
output "instance_public_ip" {
  description = "Public IP of app server"
  value       = aws_instance.app.public_ip
  sensitive   = false
}

# Module output được gọi: module.ec2.instance_public_ip
```

**Locals:** Biến trung gian, tính toán nội bộ, không thể override từ bên ngoài

```hcl
locals {
  common_tags = {
    Project     = "NoteMesh"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
  
  name_prefix = "${var.project}-${var.environment}"
}

resource "aws_instance" "app" {
  tags = local.common_tags
}
```

---

## 8. Làm sao để quản lý secrets trong Terraform?

**❌ KHÔNG làm:**
```hcl
resource "aws_db_instance" "postgres" {
  password = "MySecret123"  # Hardcode → lộ trong git, state file
}
```

**✅ Cách đúng:**

**Option 1: Biến môi trường**
```bash
export TF_VAR_db_password="MySecret123"
terraform apply
```

**Option 2: AWS Secrets Manager + data source**
```hcl
data "aws_secretsmanager_secret_version" "db_password" {
  secret_id = "notemesh/prod/db-password"
}

resource "aws_db_instance" "postgres" {
  password = jsondecode(data.aws_secretsmanager_secret_version.db_password.secret_string)["password"]
}
```

**Option 3: SSM Parameter Store**
```hcl
data "aws_ssm_parameter" "db_password" {
  name = "/notemesh/prod/db-password"
}
```

**Option 4: terraform.tfvars (thêm vào .gitignore)**
```hcl
# terraform.tfvars (KHÔNG commit)
db_password = "MySecret123"
```

> **Lưu ý:** State file vẫn lưu giá trị plain text → cần encrypt S3 backend + restrict access.

---

## 9. Terraform Workspace là gì?

**Workspace** cho phép quản lý nhiều state file độc lập trong cùng một codebase.

```bash
terraform workspace new dev       # Tạo workspace dev
terraform workspace new prod      # Tạo workspace prod
terraform workspace select dev    # Chuyển sang dev
terraform workspace list          # Liệt kê tất cả
```

**Dùng workspace trong code:**
```hcl
locals {
  instance_type = terraform.workspace == "prod" ? "t3.large" : "t3.micro"
}
```

**Thực tế:** Nhiều team dùng **separate directories** thay vì workspace vì dễ quản lý hơn:
```
environments/
├── dev/
│   └── main.tf
└── prod/
    └── main.tf
```

---

## 10. Điều gì xảy ra khi chạy `terraform destroy`?

1. Terraform đọc state file, liệt kê tất cả resource đang quản lý
2. Hiển thị plan: sẽ xóa tất cả resource đó
3. Hỏi confirm `yes`
4. Xóa resource theo **thứ tự ngược lại** với khi tạo (dependency-aware)
5. Cập nhật state file (trống)

```bash
# Destroy một resource cụ thể
terraform destroy -target=aws_instance.app

# Destroy không hỏi (CI/CD)
terraform destroy -auto-approve
```

> **⚠️ Cảnh báo:** `destroy` xóa RDS sẽ xóa luôn data! Đảm bảo có backup trước.  
> Dùng `prevent_destroy = true` để bảo vệ resource critical:

```hcl
resource "aws_db_instance" "postgres" {
  lifecycle {
    prevent_destroy = true
  }
}
```
