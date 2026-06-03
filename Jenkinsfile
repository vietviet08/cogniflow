// Jenkinsfile — Pipeline CI/CD cho NoteMesh
// Đặt file này ở root của repository

pipeline {
    agent any

    environment {
        AWS_REGION      = 'ap-southeast-1'
        S3_STATIC_BUCKET = 'notemesh-static-prod'
        CF_DISTRIBUTION_ID = credentials('cloudfront-distribution-id')
        APP_SERVER_IP   = credentials('app-server-ip')
        ECR_REPO        = '640168447652.dkr.ecr.ap-southeast-1.amazonaws.com/notemesh-api'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                echo "Branch: ${env.GIT_BRANCH} | Commit: ${env.GIT_COMMIT[0..7]}"
            }
        }

        stage('Test — API') {
            steps {
                dir('api') {
                    sh '''
                        python3.12 -m pip install -r requirements-dev.txt -q
                        PYTHONPATH=. python3.12 scripts/check_contract_sync.py
                        python3.12 -m pytest tests/ -v --tb=short
                    '''
                }
            }
        }

        stage('Test — Web') {
            steps {
                dir('web') {
                    sh '''
                        npm ci --silent
                        npm run typecheck
                        npm run test -- --run
                    '''
                }
            }
        }

        stage('Build — API Docker Image') {
            when { branch 'master' }
            steps {
                dir('api') {
                    script {
                        def tag = "${env.GIT_COMMIT[0..7]}"
                        sh """
                            docker build -t ${ECR_REPO}:${tag} .
                            docker tag ${ECR_REPO}:${tag} ${ECR_REPO}:latest
                        """
                    }
                }
            }
        }

        stage('Build — Next.js Static') {
            when { branch 'master' }
            steps {
                dir('web') {
                    sh '''
                        npm ci --silent
                        npm run build
                    '''
                }
            }
        }

        stage('Deploy — Upload Static to S3') {
            when { branch 'master' }
            steps {
                sh """
                    aws s3 sync web/out/ s3://${S3_STATIC_BUCKET}/ \
                        --delete \
                        --cache-control 'public, max-age=31536000' \
                        --exclude '*.html'
                    aws s3 sync web/out/ s3://${S3_STATIC_BUCKET}/ \
                        --delete \
                        --cache-control 'no-cache' \
                        --include '*.html'
                """
            }
        }

        stage('Deploy — CloudFront Invalidation') {
            when { branch 'master' }
            steps {
                sh """
                    aws cloudfront create-invalidation \
                        --distribution-id ${CF_DISTRIBUTION_ID} \
                        --paths "/*"
                """
            }
        }

        stage('Deploy — API to EC2') {
            when { branch 'master' }
            steps {
                script {
                    def tag = "${env.GIT_COMMIT[0..7]}"
                    sh """
                        # Login to AWS ECR
                        aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REPO}

                        # Push Docker image to ECR
                        docker push ${ECR_REPO}:${tag}
                        docker push ${ECR_REPO}:latest

                        # Chạy Ansible deploy playbook
                        ansible-playbook \
                            -i infra/ansible/inventory/hosts.ini \
                            infra/ansible/playbooks/deploy_app.yml \
                            -e "api_image_tag=${tag}" \
                            --private-key ~/.ssh/deploy_key
                    """
                }
            }
        }
    }

    post {
        success {
            echo "✅ Pipeline succeeded! Deployed commit ${env.GIT_COMMIT[0..7]}"
        }
        failure {
            echo "❌ Pipeline failed on branch ${env.GIT_BRANCH}"
        }
        always {
            cleanWs()
        }
    }
}
