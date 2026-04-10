locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

# ─── SG-ALB: chỉ nhận HTTPS/HTTP từ internet ─────────────────────────────────
resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-sg-alb"
  description = "ALB: allow HTTPS/HTTP from internet only"
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP from internet (redirect to HTTPS)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound (to EC2 targets)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name_prefix}-sg-alb" }
}

# ─── SG-APP: EC2 App Server ───────────────────────────────────────────────────
resource "aws_security_group" "app" {
  name        = "${local.name_prefix}-sg-app"
  description = "App server: FastAPI port 8000 from ALB only, SSH from your IP"
  vpc_id      = var.vpc_id

  ingress {
    description     = "FastAPI from ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    description = "SSH from your IP only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.your_ip_cidr]
  }

  egress {
    description = "Allow all outbound (OpenAI, Gemini, arXiv...)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name_prefix}-sg-app" }
}

# Cho phép Jenkins gọi API app khi deploy (thêm sau khi jenkins SG được tạo)
resource "aws_security_group_rule" "app_from_jenkins" {
  type                     = "ingress"
  description              = "Allow Jenkins to call FastAPI for health check after deploy"
  from_port                = 8000
  to_port                  = 8000
  protocol                 = "tcp"
  security_group_id        = aws_security_group.app.id
  source_security_group_id = aws_security_group.jenkins.id
}

# ─── SG-JENKINS: EC2 Jenkins Server ──────────────────────────────────────────
resource "aws_security_group" "jenkins" {
  name        = "${local.name_prefix}-sg-jenkins"
  description = "Jenkins: port 8080 from ALB only, SSH from your IP"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Jenkins UI from ALB"
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    description = "SSH from your IP only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.your_ip_cidr]
  }

  egress {
    description = "Allow all outbound (GitHub, Docker Hub, npm...)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name_prefix}-sg-jenkins" }
}

# ─── SG-RDS: PostgreSQL ───────────────────────────────────────────────────────
resource "aws_security_group" "rds" {
  name        = "${local.name_prefix}-sg-rds"
  description = "RDS: PostgreSQL port 5432 from App and Jenkins only"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from App server"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  ingress {
    description     = "PostgreSQL from Jenkins (for migrations)"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.jenkins.id]
  }

  tags = { Name = "${local.name_prefix}-sg-rds" }
}
