# ─── ALB ───────────────────────────────────────────────────
output "alb_dns_name" {
  description = "DNS name của ALB — dùng để tạo CNAME trên Hostinger"
  value       = module.alb.alb_dns_name
}

# ─── CloudFront ────────────────────────────────────────────
output "cloudfront_domain" {
  description = "CloudFront domain — dùng để tạo CNAME notemesh.catcosy.shop trên Hostinger"
  value       = module.cloudfront.cloudfront_domain_name
}

# ─── EC2 ───────────────────────────────────────────────────
output "app_server_public_ip" {
  description = "Public IP của EC2 App Server (SSH + Ansible)"
  value       = module.ec2.app_public_ip
}

output "jenkins_server_public_ip" {
  description = "Public IP của EC2 Jenkins Server (SSH + Ansible)"
  value       = module.ec2.jenkins_public_ip
}

# ─── RDS ───────────────────────────────────────────────────
output "rds_endpoint" {
  description = "Endpoint kết nối RDS PostgreSQL"
  value       = module.rds.db_endpoint
}

# ─── S3 ────────────────────────────────────────────────────
output "uploads_bucket_name" {
  description = "Tên S3 bucket lưu file uploads"
  value       = module.s3.uploads_bucket_id
}

output "static_bucket_name" {
  description = "Tên S3 bucket lưu Next.js static assets"
  value       = module.s3.static_bucket_id
}

# ─── ACM — Hướng dẫn DNS Validation ───────────────────────
output "acm_alb_validation_records" {
  description = "CNAME records cần thêm vào Hostinger để validate ACM cert cho ALB"
  value       = module.acm_alb.validation_records
}

output "acm_cloudfront_validation_records" {
  description = "CNAME records cần thêm vào Hostinger để validate ACM cert cho CloudFront"
  value       = module.acm_cloudfront.validation_records
}

# ─── Hostinger DNS Summary ─────────────────────────────────
output "hostinger_dns_instructions" {
  description = "Hướng dẫn tạo DNS records trên Hostinger"
  value = <<-EOT
    === CẤU HÌNH DNS TRÊN HOSTINGER ===

    1. notemesh.catcosy.shop  CNAME  ${module.cloudfront.cloudfront_domain_name}
    2. api.catcosy.shop       CNAME  ${module.alb.alb_dns_name}
    3. jenkins.catcosy.shop   CNAME  ${module.alb.alb_dns_name}

    + Thêm các ACM validation CNAMEs từ output acm_*_validation_records
  EOT
}
