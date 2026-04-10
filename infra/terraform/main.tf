module "vpc" {
  source               = "./modules/vpc"
  project_name         = var.project_name
  environment          = var.environment
  vpc_cidr             = var.vpc_cidr
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  availability_zones   = var.availability_zones
}

module "security_groups" {
  source       = "./modules/security_groups"
  project_name = var.project_name
  environment  = var.environment
  vpc_id       = module.vpc.vpc_id
  your_ip_cidr = var.your_ip_cidr
}

# ACM cho ALB — vùng ap-southeast-1
module "acm_alb" {
  source      = "./modules/acm"
  domain_name = var.domain_name
  san_domains = ["*.${var.domain_name}"]
}

# ACM cho CloudFront — vùng us-east-1 (bắt buộc)
module "acm_cloudfront" {
  source      = "./modules/acm"
  domain_name = "notemesh.${var.domain_name}"
  san_domains = [var.domain_name]

  providers = {
    aws = aws.us_east_1
  }
}

module "s3" {
  source              = "./modules/s3"
  project_name        = var.project_name
  environment         = var.environment
  uploads_bucket_name = var.uploads_bucket_name
  static_bucket_name  = var.static_bucket_name
}

module "rds" {
  source              = "./modules/rds"
  project_name        = var.project_name
  environment         = var.environment
  db_name             = var.db_name
  db_username         = var.db_username
  db_password         = var.db_password
  db_instance_class   = var.db_instance_class
  db_allocated_storage = var.db_allocated_storage
  db_subnet_group_name = module.vpc.db_subnet_group_name
  sg_rds_id           = module.security_groups.sg_rds_id
}

module "ec2" {
  source            = "./modules/ec2"
  project_name      = var.project_name
  environment       = var.environment
  ami_id            = var.ami_id
  instance_type     = var.ec2_instance_type
  key_pair_name     = var.key_pair_name
  public_subnet_id  = module.vpc.public_subnet_ids[0]
  sg_app_id         = module.security_groups.sg_app_id
  sg_jenkins_id     = module.security_groups.sg_jenkins_id
  uploads_bucket    = var.uploads_bucket_name
  db_host           = module.rds.db_endpoint
  db_name           = var.db_name
  db_username       = var.db_username
}

module "alb" {
  source           = "./modules/alb"
  project_name     = var.project_name
  environment      = var.environment
  vpc_id           = module.vpc.vpc_id
  public_subnet_ids = module.vpc.public_subnet_ids
  sg_alb_id        = module.security_groups.sg_alb_id
  acm_cert_arn     = module.acm_alb.certificate_arn
  app_instance_id  = module.ec2.app_instance_id
  jenkins_instance_id = module.ec2.jenkins_instance_id
  domain_name      = var.domain_name
}

module "cloudfront" {
  source             = "./modules/cloudfront"
  project_name       = var.project_name
  environment        = var.environment
  static_bucket_id   = module.s3.static_bucket_id
  static_bucket_arn  = module.s3.static_bucket_arn
  static_bucket_domain = module.s3.static_bucket_regional_domain
  acm_cert_arn       = module.acm_cloudfront.certificate_arn
  domain_aliases     = ["notemesh.${var.domain_name}"]
}
