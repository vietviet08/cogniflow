// Jenkinsfile — Pipeline CI/CD cho NoteMesh (Chỉ deploy Frontend)
// Đặt file này ở root của repository

pipeline {
    agent any

    environment {
        AWS_REGION               = 'ap-southeast-1'
        S3_STATIC_BUCKET         = 'notemesh-bucket-prod-static'
        CF_DISTRIBUTION_ID       = credentials('cloudfront-distribution-id')
        NEXT_PUBLIC_API_BASE_URL = 'https://api-notemesh.vietnq.online/api/v1'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                echo "Branch: ${env.GIT_BRANCH} | Commit: ${env.GIT_COMMIT[0..7]}"
            }
        }

        stage('Build — Next.js Static') {
            when { expression { env.GIT_BRANCH?.contains('master') } }
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
            when { expression { env.GIT_BRANCH?.contains('master') } }
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
            when { expression { env.GIT_BRANCH?.contains('master') } }
            steps {
                sh """
                    aws cloudfront create-invalidation \
                        --distribution-id ${CF_DISTRIBUTION_ID} \
                        --paths "/*"
                """
            }
        }
    }

    post {
        success {
            echo "✅ Pipeline succeeded! Deployed frontend commit ${env.GIT_COMMIT[0..7]}"
        }
        failure {
            echo "❌ Pipeline failed on branch ${env.GIT_BRANCH}"
        }
        always {
            cleanWs()
        }
    }
}
