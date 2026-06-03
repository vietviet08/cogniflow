terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}

resource "aws_acm_certificate" "main" {
  domain_name               = var.domain_name
  subject_alternative_names = var.san_domains
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = { Name = var.domain_name }
}
