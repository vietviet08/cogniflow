# 💬 Câu hỏi Behavioral

---

## 1. Kể về một lần bạn debug một lỗi khó. Bạn đã tiếp cận như thế nào?

**Framework trả lời: STAR (Situation → Task → Action → Result)**

**Ví dụ câu trả lời (dùng dự án NoteMesh):**

> **Situation:** Trong dự án NoteMesh, sau khi deploy lên AWS, service API trả về lỗi 502 Bad Gateway từ ALB nhưng chỉ xảy ra với một số request nhất định, không phải tất cả.
>
> **Task:** Tôi cần xác định nguyên nhân và fix trong khi service đang chạy production.
>
> **Action:** Tôi tiếp cận theo từng bước:
> 1. Kiểm tra ALB access logs → thấy một số request có target response time = -1 (timeout)
> 2. SSH vào EC2, kiểm tra container logs → thấy một số request bị OOM killed
> 3. `docker stats` → container dùng memory quá mức limit đã set
> 4. Phân tích những request bị lỗi → đều là upload file lớn
> 5. Root cause: Không có limit upload size, file lớn consume hết memory container
>
> **Result:** Fix bằng cách thêm upload size limit trong API và tăng memory limit container. Sau đó implement streaming upload thay vì load toàn bộ file vào memory. 502 errors giảm về 0.

**Điểm quan trọng khi trả lời:**
- Mô tả **quy trình tư duy** có hệ thống (không đoán mò)
- Dùng **data/metrics** để confirm giả thuyết
- Nói về **lesson learned** (lần sau làm gì để phòng tránh)
- Chứng minh khả năng **không panic** dưới áp lực

---

## 2. Bạn làm gì khi gặp một công nghệ hoàn toàn mới?

**Gợi ý framework trả lời:**

> Khi gặp công nghệ mới như Terraform hay Ansible, tôi thường:
>
> 1. **Hiểu big picture trước:** Đọc official documentation phần Getting Started, xem architecture overview để biết nó giải quyết vấn đề gì.
>
> 2. **Hands-on ngay:** Không chỉ đọc lý thuyết. Tôi setup môi trường local và thực hành với use case đơn giản nhất.
>
> 3. **Học qua project thực:** Áp dụng vào dự án thực (như NoteMesh) thay vì chỉ làm tutorial. Gặp vấn đề thực tế mới hiểu sâu.
>
> 4. **Tận dụng community:** GitHub issues, Stack Overflow, official Slack/Discord. Đa số vấn đề đã có người hỏi rồi.
>
> 5. **Ghi chép lại:** Tạo notes về những gì học được, gotchas, best practices để sau này tham khảo.
>
> Ví dụ: Khi học Terraform, tôi bắt đầu bằng cách đọc docs 30 phút, sau đó tự tay provision một EC2 instance, rồi mới apply vào NoteMesh infrastructure.

---

## 3. Tại sao bạn muốn làm Infra/DevOps thay vì Dev thuần?

**Gợi ý trả lời chân thật:**

> Tôi thấy mình hứng thú hơn với việc **hiểu how things work** ở tầng nền tảng. Khi tôi deploy ứng dụng lên AWS và thấy nó chạy ổn định, có cảm giác thỏa mãn đặc biệt so với chỉ viết feature.
>
> Điều tôi thích ở Infra/DevOps:
> - **Impact scale rộng hơn:** Một thay đổi infrastructure ảnh hưởng đến toàn bộ team developer và hệ thống
> - **Problem diversity:** Mỗi ngày gặp vấn đề ở nhiều tầng khác nhau - network, OS, cloud, security...
> - **Hands-on với technology thật:** Không chỉ là abstractions, mà là servers, networks, databases thật sự
> - **DevOps culture:** Kéo gần khoảng cách giữa development và operations
>
> Dự án NoteMesh giúp tôi confirm điều này - tôi enjoy việc thiết kế AWS architecture và viết Terraform/Ansible hơn là viết API endpoints.

---

## 4. Kể về dự án cá nhân/trường học liên quan đến infra của bạn.

**Cách khai thác dự án NoteMesh:**

> **Dự án NoteMesh** - Ứng dụng ghi chú thông minh với AI integration.
>
> **Tôi đảm nhiệm phần infrastructure:**
>
> **Architecture:** Thiết kế AWS infrastructure gồm:
> - VPC với Public/Private subnets trên 2 AZ
> - ALB làm entry point, host-based routing đến App EC2 và Jenkins EC2
> - RDS PostgreSQL ở Private Subnet
> - S3 cho file storage với CloudFront CDN
> - ACM certificates cho HTTPS
>
> **Infrastructure as Code với Terraform:**
> - Tổ chức theo modules (vpc, ec2, rds, s3, acm, alb, security_groups)
> - Remote state trên S3 + DynamoDB locking
> - Variables và outputs để dễ customize theo environment
>
> **Configuration Management với Ansible:**
> - Roles cho Docker installation, app deployment
> - Ansible Vault cho secrets management
> - Dynamic inventory từ EC2 tags
>
> **CI/CD với Jenkins:**
> - Pipeline: Build Docker image → Push ECR → Deploy via Ansible
> - Webhook trigger từ GitHub
>
> **Challenges tôi gặp và giải quyết:**
> - [Mô tả 1-2 vấn đề thực tế và cách fix]

---

## 5. Bạn đang học gì để improve bản thân trong lĩnh vực này?

**Gợi ý:**

> Hiện tại tôi đang focus vào:
>
> **Ngắn hạn (đang học):**
> - Hoàn thiện AWS knowledge: Chuẩn bị cho AWS SAA (Solutions Architect Associate)
> - Kubernetes cơ bản: Học cách orchestrate containers ở scale lớn hơn
> - Monitoring stack: Prometheus + Grafana để observability
>
> **Đang thực hành qua dự án NoteMesh:**
> - Apply Terraform best practices vào production-like environment
> - Implement proper CI/CD pipeline với Jenkins
> - Cấu hình Ansible roles chuẩn production
>
> **Dài hạn:**
> - Site Reliability Engineering (SRE) practices: SLO, error budgets, runbooks
> - Platform engineering: Xây dựng internal developer platform
>
> Tôi cũng hay đọc:
> - AWS Blog và What's New để cập nhật services mới
> - The DevOps Handbook
> - Google SRE Book (free online)

---

## 📌 Tips chung cho Behavioral Interview

### Framework STAR:
- **S**ituation: Bối cảnh
- **T**ask: Nhiệm vụ của bạn
- **A**ction: Bạn đã làm gì (chi tiết, quantified)
- **R**esult: Kết quả đạt được

### Những điều nên làm:
- ✅ Chuẩn bị 5-7 câu chuyện thực tế từ dự án của mình
- ✅ Dùng số liệu cụ thể ("giảm 80% build time", "xử lý 1000 request/s")
- ✅ Honest về những lần thất bại và lesson learned
- ✅ Thể hiện **ownership** - bạn tự chủ động, không chờ được giao việc
- ✅ Kết nối câu trả lời với skills/values của công ty

### Những điều không nên làm:
- ❌ Nói xấu team/manager cũ
- ❌ Câu chuyện không có action cụ thể (chỉ describe problem)
- ❌ Câu trả lời quá dài, lan man
- ❌ Không có kết quả rõ ràng
