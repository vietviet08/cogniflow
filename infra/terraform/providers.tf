terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Uncomment to use S3 remote state (recommended for team)
  # backend "s3" {
  #   bucket = "notemesh-terraform-state"
  #   key    = "prod/terraform.tfstate"
  #   region = "ap-southeast-1"
  # }
}

# Default provider — ap-southeast-1 (Singapore, gần VN)
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# Provider alias — us-east-1 (bắt buộc cho ACM cấp CloudFront)
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}
