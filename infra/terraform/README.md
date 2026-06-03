# Terraform

This stack creates:

- VPC with public subnets for ALB/EC2 and private subnets for RDS
- Security groups
- ACM certificates for ALB hostnames and CloudFront frontend hostname
- One EC2 server running Docker Compose services and Jenkins
- RDS PostgreSQL
- Private uploads S3 bucket and static web S3 bucket
- CloudFront distribution for the static frontend
- ALB routing to nginx on EC2

Use a two-step apply when using Hostinger DNS:

1. Keep `enable_custom_domains = false`, run `terraform apply`, and add ACM validation CNAMEs in Hostinger.
2. Wait until certificates are `ISSUED`, set `enable_custom_domains = true`, and run `terraform apply` again.

See `../README.md` for the end-to-end deployment flow.
