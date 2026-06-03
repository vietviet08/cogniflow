# NoteMesh AWS Infrastructure

Target architecture:

```text
notemesh.vietnq.online            -> CloudFront -> S3 static web bucket
api-notemesh.vietnq.online        -> ALB -> app EC2 nginx -> FastAPI container
pgadmin-notemesh.vietnq.online    -> ALB -> app EC2 nginx -> pgAdmin container
jenkins-notemesh.vietnq.online      -> ALB -> Jenkins EC2 nginx -> Jenkins service

FastAPI container -> RDS PostgreSQL
FastAPI/worker    -> ChromaDB container on app EC2
FastAPI/worker    -> private S3 uploads bucket
```

## Terraform

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Fill key_pair_name, your_ip_cidr, db_password, and globally unique bucket names.

terraform init
terraform apply
```

The first apply creates ACM certificates but keeps `enable_custom_domains = false`, because Hostinger DNS validation records do not exist yet.

After the first apply, add these records in Hostinger:

- All CNAMEs from `terraform output acm_alb_validation_records`
- All CNAMEs from `terraform output acm_cloudfront_validation_records`
- `${frontend_domain}` CNAME to `terraform output cloudfront_domain`
- `${api_domain}` CNAME to `terraform output alb_dns_name`
- `${pgadmin_domain}` CNAME to `terraform output alb_dns_name`
- `${jenkins_domain}` CNAME to `terraform output alb_dns_name`

When both ACM certificates are `ISSUED`, set this in `terraform.tfvars`:

```hcl
enable_custom_domains = true
```

Then run:

```bash
terraform apply
```

## Ansible

Update inventory from Terraform outputs:

```bash
terraform -chdir=infra/terraform output app_server_public_ip
terraform -chdir=infra/terraform output jenkins_server_public_ip
```

Edit:

- `infra/ansible/inventory/hosts.ini`
- `infra/ansible/group_vars/app_servers.yml`

Encrypt real secrets with `ansible-vault`.

Run:

```bash
cd infra/ansible
ansible all -i inventory/hosts.ini -m ping
ansible-playbook -i inventory/hosts.ini site.yml
```

## Verify

```bash
curl https://api-notemesh.vietnq.online/api/v1/health
open https://pgadmin-notemesh.vietnq.online
open https://jenkins-notemesh.vietnq.online
open https://notemesh.vietnq.online
```

## Frontend Deploy

Build and upload the static export:

```bash
cd web
npm ci
NEXT_PUBLIC_API_BASE_URL=https://api-notemesh.vietnq.online/api/v1 npm run build
aws s3 sync out/ s3://notemesh-static-prod/ --delete
aws cloudfront create-invalidation --distribution-id <cloudfront_distribution_id> --paths "/*"
```
