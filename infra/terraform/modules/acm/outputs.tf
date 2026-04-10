output "certificate_arn" {
  value = aws_acm_certificate.main.arn
}

# Output các CNAME records cần thêm vào Hostinger để validate cert
output "validation_records" {
  description = "Thêm các records này vào Hostinger DNS Manager"
  value = {
    for dvo in aws_acm_certificate.main.domain_validation_options : dvo.domain_name => {
      name  = dvo.resource_record_name
      type  = dvo.resource_record_type
      value = dvo.resource_record_value
    }
  }
}
