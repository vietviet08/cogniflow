variable "project_name"             { type = string }
variable "environment"               { type = string }
variable "static_bucket_id"         { type = string }
variable "static_bucket_arn"        { type = string }
variable "static_bucket_domain"     { type = string }
variable "acm_cert_arn"             { type = string }
variable "domain_aliases"           { type = list(string) }
