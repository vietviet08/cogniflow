# 🔄 CI/CD & DevOps

---

## 1. CI/CD là gì? Giải thích sự khác nhau giữa CI và CD.

**CI (Continuous Integration):** Tự động build và test code mỗi khi developer push/merge code.

**CD (Continuous Delivery):** Tự động đưa code đã test ra staging/pre-prod, cần manual approval để lên prod.

**CD (Continuous Deployment):** Tự động đưa code lên production không cần manual approval.

```
Developer push code
       ↓
┌─────────────────────────────────────────┐
│              CI Pipeline                │
│  Build → Unit Test → Integration Test  │
│  → Code Quality → Security Scan         │
└────────────────────┬────────────────────┘
                     ↓ Artifact (Docker image, JAR...)
┌─────────────────────────────────────────┐
│         Continuous Delivery             │
│  Deploy to Staging → E2E Tests          │
│  → Manual Approval → Deploy to Prod     │ ← CD (Delivery)
├─────────────────────────────────────────┤
│         Continuous Deployment           │
│  Deploy to Staging → E2E Tests          │
│  → Auto Deploy to Prod (no approval)    │ ← CD (Deployment)
└─────────────────────────────────────────┘
```

**Lợi ích:**
- Phát hiện bug sớm (fail fast)
- Giảm integration hell
- Deployment nhanh hơn, ít rủi ro hơn
- Feedback loop ngắn hơn cho developer

---

## 2. Pipeline điển hình gồm những stage nào?

```
┌──────────────────────────────────────────────────────────────────┐
│                     CI/CD Pipeline                               │
├──────────┬──────────┬──────────┬──────────┬─────────┬──────────┤
│  Source  │  Build   │   Test   │  Scan    │  Deploy │  Verify  │
├──────────┼──────────┼──────────┼──────────┼─────────┼──────────┤
│ git push │ compile  │ unit     │ SAST     │ staging │ smoke    │
│ PR merge │ docker   │ integ    │ SCA      │ prod    │ test     │
│          │ build    │ e2e      │ container│         │ monitor  │
│          │          │ perf     │ scan     │         │          │
└──────────┴──────────┴──────────┴──────────┴─────────┴──────────┘
```

**Stage cụ thể:**

1. **Source:** Trigger (push to main, PR opened)
2. **Build:** Compile code, build Docker image, tag với commit SHA
3. **Test:**
   - Unit tests (fast, isolated)
   - Integration tests (with DB, Redis...)
   - End-to-end tests (Playwright, Selenium)
4. **Security Scan:**
   - SAST: Code analysis (SonarQube, Semgrep)
   - SCA: Dependency vulnerabilities (Snyk, Trivy)
   - Container scan: Image vulnerabilities
5. **Push Artifact:** Push Docker image lên ECR/Docker Hub
6. **Deploy Staging:** Deploy lên môi trường staging
7. **E2E on Staging:** Smoke tests, performance tests
8. **Manual Approval:** (Continuous Delivery mode)
9. **Deploy Production:** Blue/green hoặc rolling deployment
10. **Post-deploy verify:** Health checks, rollback nếu fail

---

## 3. Jenkins là gì? Jenkinsfile là gì?

**Jenkins** là CI/CD server mã nguồn mở, tự host, có ecosystem plugin phong phú.

**Kiến trúc Jenkins:**
```
Jenkins Master
├── Job scheduling
├── Plugin management
└── Agents (Workers) → Chạy actual build
    ├── Agent 1 (Linux)
    ├── Agent 2 (Windows)
    └── Agent 3 (Docker)
```

**Jenkinsfile** (Pipeline as Code): File định nghĩa CI/CD pipeline, lưu trong git cùng source code.

```groovy
// Jenkinsfile (Declarative Pipeline)
pipeline {
    agent any

    environment {
        ECR_REGISTRY = "123456789.dkr.ecr.ap-southeast-1.amazonaws.com"
        IMAGE_NAME    = "notemesh-api"
        IMAGE_TAG     = "${env.GIT_COMMIT[0..7]}"
    }

    stages {
        stage('Checkout') {
            steps {
                git branch: 'main', url: 'https://github.com/org/notemesh.git'
            }
        }

        stage('Test') {
            steps {
                sh 'npm ci'
                sh 'npm run test:coverage'
            }
            post {
                always {
                    publishTestResults testResultsPattern: 'test-results/*.xml'
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    sh "docker build -t ${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} ."
                }
            }
        }

        stage('Push to ECR') {
            steps {
                withCredentials([aws(credentialsId: 'aws-creds')]) {
                    sh "aws ecr get-login-password | docker login --username AWS --password-stdin ${ECR_REGISTRY}"
                    sh "docker push ${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
                }
            }
        }

        stage('Deploy to Staging') {
            steps {
                sh "ansible-playbook -i inventory/staging deploy.yml -e image_tag=${IMAGE_TAG}"
            }
        }

        stage('Deploy to Production') {
            when { branch 'main' }
            input { message "Deploy to production?" }
            steps {
                sh "ansible-playbook -i inventory/prod deploy.yml -e image_tag=${IMAGE_TAG}"
            }
        }
    }

    post {
        success { slackSend message: "✅ Build ${IMAGE_TAG} deployed successfully" }
        failure { slackSend message: "❌ Build ${IMAGE_TAG} failed!" }
    }
}
```

---

## 4. Blue/Green Deployment vs Rolling vs Canary Release?

**Blue/Green Deployment:**
```
Before: 100% traffic → Blue (old version)
During: Tạo Green (new version), switch traffic ngay lập tức
After:  100% traffic → Green (new version)
Blue vẫn tồn tại → rollback ngay nếu cần

Pros: Zero downtime, rollback nhanh
Cons: Cần gấp đôi resources trong quá trình deploy
```

**Rolling Deployment:**
```
v1  v1  v1  v1  (ban đầu 4 instances)
v2  v1  v1  v1  (replace lần lượt)
v2  v2  v1  v1
v2  v2  v2  v1
v2  v2  v2  v2  (xong)

Pros: Không cần double resources
Cons: Chạy 2 version cùng lúc trong quá trình deploy
```

**Canary Release:**
```
v1  v1  v1  v1  (100% traffic)
v2  v1  v1  v1  (5% traffic → v2, monitor metrics)
v2  v2  v1  v1  (20% traffic → v2, nếu OK)
v2  v2  v2  v2  (100% nếu ổn định)

Pros: Test với real traffic, ít rủi ro
Cons: Phức tạp, cần feature flags/routing logic
```

---

## 5. Artifact trong CI/CD là gì?

**Artifact** là output của build process, được lưu trữ để deploy.

| Type | Ví dụ | Lưu ở đâu |
|------|-------|-----------|
| Docker Image | `notemesh-api:abc1234` | ECR, Docker Hub, GCR |
| JAR/WAR | `app-1.2.3.jar` | Nexus, Artifactory, S3 |
| Binary | `myapp-linux-amd64` | S3, GitHub Releases |
| Frontend bundle | `dist/*.js, *.css` | S3, CDN |
| Helm chart | `myapp-1.2.3.tgz` | Chart Museum, OCI registry |

**Versioning artifact:**
- Dùng **Git commit SHA**: `notemesh-api:a3b2c1d` (immutable, traceable)
- Dùng **semantic version**: `notemesh-api:1.2.3`
- Dùng **branch + build number**: `notemesh-api:main-42`
- **Không dùng `latest`** trong production (không rõ version nào)

---

## 6. Webhook là gì? Jenkins dùng webhook để làm gì?

**Webhook** là HTTP callback - khi sự kiện X xảy ra ở hệ thống A, tự động gửi HTTP POST đến hệ thống B.

**GitHub → Jenkins Webhook:**
```
Developer push code lên GitHub
         ↓
GitHub gửi POST request đến:
https://jenkins.notemesh.com/github-webhook/
         ↓
Jenkins nhận webhook → trigger build pipeline ngay lập tức
```

**Cấu hình trên GitHub:**
```
Repository Settings → Webhooks → Add webhook
URL: https://jenkins.notemesh.com/github-webhook/
Content type: application/json
Events: Push events, Pull request events
```

**Cấu hình trong Jenkins:**
```
Job → Build Triggers → ✅ GitHub hook trigger for GITScm polling
```

**So sánh Webhook vs Polling:**
| | Webhook | Polling |
|-|---------|---------|
| Trigger | Ngay khi có event | Jenkins hỏi định kỳ (mỗi 5 phút) |
| Latency | Thấp (real-time) | Cao (đến 5 phút) |
| Resource | Hiệu quả | Lãng phí request |
| Phức tạp | Cần public URL | Đơn giản hơn |
