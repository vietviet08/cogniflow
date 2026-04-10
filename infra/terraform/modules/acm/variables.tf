variable "domain_name" {
  description = "Primary domain cho certificate"
  type        = string
}

variable "san_domains" {
  description = "Subject Alternative Names (wildcard hoặc additional domains)"
  type        = list(string)
  default     = []
}
