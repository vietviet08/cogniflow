output "app_instance_id"  { value = aws_instance.app.id }
output "app_public_ip"    { value = aws_instance.app.public_ip }
output "app_private_ip"   { value = aws_instance.app.private_ip }

output "jenkins_instance_id" { value = aws_instance.jenkins.id }
output "jenkins_public_ip"   { value = aws_instance.jenkins.public_ip }
output "jenkins_private_ip"  { value = aws_instance.jenkins.private_ip }
