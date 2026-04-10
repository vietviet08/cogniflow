output "uploads_bucket_id"              { value = aws_s3_bucket.uploads.id }
output "uploads_bucket_arn"             { value = aws_s3_bucket.uploads.arn }
output "static_bucket_id"               { value = aws_s3_bucket.static.id }
output "static_bucket_arn"              { value = aws_s3_bucket.static.arn }
output "static_bucket_regional_domain"  { value = aws_s3_bucket.static.bucket_regional_domain_name }
