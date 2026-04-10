output "sg_alb_id"     { value = aws_security_group.alb.id }
output "sg_app_id"     { value = aws_security_group.app.id }
output "sg_jenkins_id" { value = aws_security_group.jenkins.id }
output "sg_rds_id"     { value = aws_security_group.rds.id }
