variable "aws_region" {
  description = "AWS region chính"
  type        = string
  default     = "ap-southeast-1"
}

variable "project_name" {
  description = "Tên project, dùng làm prefix cho tất cả resource"
  type        = string
  default     = "notemesh"
}

variable "environment" {
  description = "Môi trường: dev | staging | prod"
  type        = string
  default     = "prod"
}

# ─── Domain ────────────────────────────────────────────────
variable "domain_name" {
  description = "Domain gốc (không có www)"
  type        = string
  default     = "catcosy.shop"
}

# ─── Network ───────────────────────────────────────────────
variable "vpc_cidr" {
  description = "CIDR block cho VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR của 2 public subnets (ALB cần ≥2 AZ)"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR của 2 private subnets (RDS)"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

variable "availability_zones" {
  description = "AZs sử dụng trong region"
  type        = list(string)
  default     = ["ap-southeast-1a", "ap-southeast-1b"]
}

# ─── EC2 ───────────────────────────────────────────────────
variable "ec2_instance_type" {
  description = "Instance type cho cả 2 EC2"
  type        = string
  default     = "t3.medium"
}

variable "key_pair_name" {
  description = "Tên EC2 Key Pair đã tạo sẵn trên AWS (dùng để SSH)"
  type        = string
}

variable "ami_id" {
  description = "AMI ID cho EC2 (Ubuntu 22.04 LTS ap-southeast-1)"
  type        = string
  default     = "ami-0df7a207adb9748c7" # Ubuntu 22.04 LTS (ap-southeast-1)
}

variable "your_ip_cidr" {
  description = "IP của bạn để mở SSH, format: x.x.x.x/32"
  type        = string
}

# ─── RDS ───────────────────────────────────────────────────
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_name" {
  description = "Tên database"
  type        = string
  default     = "notemesh"
}

variable "db_username" {
  description = "Username của PostgreSQL"
  type        = string
  default     = "notemesh_admin"
}

variable "db_password" {
  description = "Password của PostgreSQL (sensitive)"
  type        = string
  sensitive   = true
}

variable "db_allocated_storage" {
  description = "Dung lượng lưu trữ RDS (GB)"
  type        = number
  default     = 20
}

# ─── S3 ────────────────────────────────────────────────────
variable "uploads_bucket_name" {
  description = "Tên S3 bucket lưu file uploads"
  type        = string
  default     = "notemesh-uploads"
}

variable "static_bucket_name" {
  description = "Tên S3 bucket lưu Next.js static export"
  type        = string
  default     = "notemesh-static"
}
