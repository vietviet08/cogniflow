output "alb_dns_name" {
  description = "ALB DNS name. Create Hostinger CNAME records for API, pgAdmin, and Jenkins to this value."
  value       = module.alb.alb_dns_name
}

output "cloudfront_domain" {
  description = "CloudFront DNS name. Create the Hostinger CNAME record for the frontend to this value."
  value       = module.cloudfront.cloudfront_domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID used by CI/CD invalidations."
  value       = module.cloudfront.cloudfront_distribution_id
}

output "app_server_public_ip" {
  description = "Public IP of the single EC2 server running Docker Compose and Jenkins."
  value       = module.ec2.app_public_ip
}

output "jenkins_server_public_ip" {
  description = "Same as app_server_public_ip. Jenkins runs on the single app EC2 server."
  value       = module.ec2.app_public_ip
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint."
  value       = module.rds.db_endpoint
}

output "uploads_bucket_name" {
  description = "Private S3 bucket for uploaded source files."
  value       = module.s3.uploads_bucket_id
}

output "static_bucket_name" {
  description = "S3 bucket for Next.js static export files."
  value       = module.s3.static_bucket_id
}

output "frontend_domain" {
  value = var.frontend_domain
}

output "api_domain" {
  value = var.api_domain
}

output "pgadmin_domain" {
  value = var.pgadmin_domain
}

output "jenkins_domain" {
  value = var.jenkins_domain
}

output "acm_alb_validation_records" {
  description = "Add these CNAME records in Hostinger to validate the ALB certificate."
  value       = module.acm_alb.validation_records
}

output "acm_cloudfront_validation_records" {
  description = "Add these CNAME records in Hostinger to validate the CloudFront certificate."
  value       = module.acm_cloudfront.validation_records
}

output "hostinger_dns_instructions" {
  description = "DNS records to create in Hostinger after Terraform apply."
  value       = <<-EOT
    Hostinger DNS records:

    ${var.frontend_domain}  CNAME  ${module.cloudfront.cloudfront_domain_name}
    ${var.api_domain}       CNAME  ${module.alb.alb_dns_name}
    ${var.pgadmin_domain}   CNAME  ${module.alb.alb_dns_name}
    ${var.jenkins_domain}   CNAME  ${module.alb.alb_dns_name}

    Also add all ACM validation CNAME records from:
    - acm_alb_validation_records
    - acm_cloudfront_validation_records

    Initial apply uses the default CloudFront certificate and HTTP ALB listener.
    After ACM certificates become ISSUED, set enable_custom_domains = true and run terraform apply again.
  EOT
}

output "ecr_repository_url" {
  description = "ECR Docker repository URL."
  value       = aws_ecr_repository.api.repository_url
}
