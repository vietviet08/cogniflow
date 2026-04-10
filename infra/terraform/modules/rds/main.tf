locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

resource "aws_db_instance" "main" {
  identifier        = "${local.name_prefix}-postgres"
  engine            = "postgres"
  engine_version    = "16.4"
  instance_class    = var.db_instance_class
  allocated_storage = var.db_allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = var.db_subnet_group_name
  vpc_security_group_ids = [var.sg_rds_id]

  backup_retention_period = 7           # giữ backup 7 ngày
  backup_window           = "03:00-04:00" # 3-4 AM UTC (10-11 AM +7)
  maintenance_window      = "Sun:04:00-Sun:05:00"

  skip_final_snapshot       = false
  final_snapshot_identifier = "${local.name_prefix}-final-snapshot"
  deletion_protection       = false  # Đổi thành true khi production ổn định

  # Performance Insights (miễn phí cho t3.micro)
  performance_insights_enabled = true

  tags = { Name = "${local.name_prefix}-postgres" }
}
