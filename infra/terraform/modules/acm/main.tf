# Certificate sử dụng DNS validation
# Sau khi apply, cần thêm các CNAME records vào Hostinger (xem output)
resource "aws_acm_certificate" "main" {
  domain_name               = var.domain_name
  subject_alternative_names = var.san_domains
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = { Name = var.domain_name }
}

# Lưu ý: aws_acm_certificate_validation bị bỏ qua ở đây
# vì validation cần thêm CNAME thủ công vào Hostinger.
# Certificate sẽ PENDING_VALIDATION cho đến khi bạn thêm CNAME.
