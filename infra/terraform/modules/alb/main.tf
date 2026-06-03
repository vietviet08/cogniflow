locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

resource "aws_lb" "main" {
  name               = "${local.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.sg_alb_id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection = false

  tags = { Name = "${local.name_prefix}-alb" }
}

resource "aws_lb_target_group" "app_nginx" {
  name        = "${local.name_prefix}-tg-app"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "instance"

  health_check {
    enabled             = true
    path                = "/api/v1/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }

  tags = { Name = "${local.name_prefix}-tg-app" }
}

resource "aws_lb_target_group_attachment" "app_nginx" {
  target_group_arn = aws_lb_target_group.app_nginx.arn
  target_id        = var.app_instance_id
  port             = 80
}

resource "aws_lb_target_group" "jenkins_nginx" {
  name        = "${local.name_prefix}-tg-jenkins"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "instance"

  health_check {
    enabled             = true
    path                = "/login"
    port                = "traffic-port"
    protocol            = "HTTP"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }

  tags = { Name = "${local.name_prefix}-tg-jenkins" }
}

resource "aws_lb_target_group_attachment" "jenkins_nginx" {
  target_group_arn = aws_lb_target_group.jenkins_nginx.arn
  target_id        = var.jenkins_instance_id
  port             = 80
}

resource "aws_lb_listener" "http_forward" {
  count = var.enable_https ? 0 : 1

  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app_nginx.arn
  }
}

resource "aws_lb_listener" "http_redirect" {
  count = var.enable_https ? 1 : 0

  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  count = var.enable_https ? 1 : 0

  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_cert_arn

  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = "Not Found"
      status_code  = "404"
    }
  }
}

resource "aws_lb_listener_rule" "api" {
  count = var.enable_https ? 1 : 0

  listener_arn = aws_lb_listener.https[0].arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app_nginx.arn
  }

  condition {
    host_header {
      values = [var.api_domain]
    }
  }
}

resource "aws_lb_listener_rule" "pgadmin" {
  count = var.enable_https ? 1 : 0

  listener_arn = aws_lb_listener.https[0].arn
  priority     = 20

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app_nginx.arn
  }

  condition {
    host_header {
      values = [var.pgadmin_domain]
    }
  }
}

resource "aws_lb_listener_rule" "jenkins" {
  count = var.enable_https ? 1 : 0

  listener_arn = aws_lb_listener.https[0].arn
  priority     = 30

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.jenkins_nginx.arn
  }

  condition {
    host_header {
      values = [var.jenkins_domain]
    }
  }
}
