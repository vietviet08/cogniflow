locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

# ─── IAM Role cho EC2 App (quyền đọc/ghi S3) ─────────────────────────────────
resource "aws_iam_role" "app_ec2_role" {
  name = "${local.name_prefix}-app-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "app_s3_policy" {
  name = "${local.name_prefix}-app-s3-policy"
  role = aws_iam_role.app_ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::${var.uploads_bucket}",
          "arn:aws:s3:::${var.uploads_bucket}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_instance_profile" "app" {
  name = "${local.name_prefix}-app-instance-profile"
  role = aws_iam_role.app_ec2_role.name
}

# ─── IAM Role cho Jenkins EC2 (quyền ECR, S3 static) ─────────────────────────
resource "aws_iam_role" "jenkins_ec2_role" {
  name = "${local.name_prefix}-jenkins-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "jenkins_policy" {
  name = "${local.name_prefix}-jenkins-policy"
  role = aws_iam_role.jenkins_ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject", "s3:GetObject", "s3:DeleteObject",
          "s3:ListBucket", "s3:PutBucketWebsite"
        ]
        Resource = ["arn:aws:s3:::*"]
      },
      {
        Effect   = "Allow"
        Action   = ["ecr:*"]
        Resource = ["*"]
      },
      {
        Effect   = "Allow"
        Action   = ["cloudfront:CreateInvalidation"]
        Resource = ["*"]
      }
    ]
  })
}

resource "aws_iam_instance_profile" "jenkins" {
  name = "${local.name_prefix}-jenkins-instance-profile"
  role = aws_iam_role.jenkins_ec2_role.name
}

# ─── EC2 App Server ───────────────────────────────────────────────────────────
resource "aws_instance" "app" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_pair_name
  subnet_id              = var.public_subnet_id
  vpc_security_group_ids = [var.sg_app_id]
  iam_instance_profile   = aws_iam_instance_profile.app.name

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 30
    delete_on_termination = true
    encrypted             = true
  }

  # User data: cài Docker + Docker Compose khi khởi động lần đầu
  user_data = base64encode(templatefile("${path.module}/../../scripts/user_data_app.sh", {
    db_host     = var.db_host
    db_name     = var.db_name
    db_username = var.db_username
    aws_region  = "ap-southeast-1"
    s3_bucket   = var.uploads_bucket
  }))

  tags = {
    Name = "${local.name_prefix}-app-server"
    Role = "app"
  }
}

# ─── EC2 Jenkins Server ───────────────────────────────────────────────────────
resource "aws_instance" "jenkins" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_pair_name
  subnet_id              = var.public_subnet_id
  vpc_security_group_ids = [var.sg_jenkins_id]
  iam_instance_profile   = aws_iam_instance_profile.jenkins.name

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 30
    delete_on_termination = true
    encrypted             = true
  }

  user_data = base64encode(file("${path.module}/../../scripts/user_data_jenkins.sh"))

  tags = {
    Name = "${local.name_prefix}-jenkins-server"
    Role = "jenkins"
  }
}
