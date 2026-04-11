# ☁️ Cloud / AWS

---

## 1. Region và Availability Zone (AZ) khác nhau thế nào?

| | Region | Availability Zone (AZ) |
|-|--------|------------------------|
| Định nghĩa | Vị trí địa lý (ví dụ: Singapore, Tokyo) | Data center riêng biệt trong một Region |
| Số lượng | ~30+ regions toàn cầu | 2-6 AZ mỗi Region |
| Khoảng cách | Cách nhau hàng nghìn km | Cách nhau vài km, kết nối tốc độ cao |
| Mục đích | Giảm latency theo vùng địa lý | High availability, fault isolation |

**Ví dụ:** `ap-southeast-1` (Singapore) có 3 AZ: `ap-southeast-1a`, `1b`, `1c`.

**Best practice:** Deploy sang nhiều AZ để đảm bảo HA (High Availability). Nếu một AZ bị sự cố, AZ còn lại vẫn phục vụ được.

```
Region: ap-southeast-1
├── AZ: ap-southeast-1a → EC2, RDS Primary
├── AZ: ap-southeast-1b → EC2 (standby), RDS Replica
└── AZ: ap-southeast-1c → (backup)
```

---

## 2. EC2 instance types khác nhau ở điểm gì?

Instance type format: `[family][generation][attribute].[size]`

Ví dụ: `t3.medium`, `c5.xlarge`, `m5.2xlarge`

| Family | Tối ưu cho | Ví dụ use case |
|--------|-----------|----------------|
| `t` (General burstable) | Workload không đều, dev/test | t3.micro (free tier) |
| `m` (General purpose) | Web servers, app servers | m5.large |
| `c` (Compute optimized) | CPU-intensive: batch, encoding | c5.xlarge |
| `r` (Memory optimized) | Database, in-memory cache | r5.2xlarge |
| `g/p` (GPU) | ML training, rendering | g4dn.xlarge |
| `i` (Storage optimized) | NoSQL, data warehousing | i3.large |

**T-series Burstable:** Có CPU credit. Khi idle tích lũy credit, khi cần burst sẽ dùng credit. Rẻ hơn nhưng không phù hợp với workload liên tục cao.

**Sizes:** nano < micro < small < medium < large < xlarge < 2xlarge...

---

## 3. S3 là gì? Giải thích S3 storage classes.

**S3 (Simple Storage Service):** Object storage, lưu file dưới dạng object trong bucket.

- **Unlimited storage**, scalable
- **11 nines (99.999999999%)** durability
- Object có thể lên đến **5TB**
- Access qua URL hoặc API

**Storage Classes:**

| Class | Use case | Retrieval | Chi phí |
|-------|----------|-----------|---------|
| **Standard** | Thường xuyên truy cập | Tức thì | Cao nhất |
| **Standard-IA** | Ít truy cập, cần ngay khi cần | Tức thì | Thấp hơn |
| **One Zone-IA** | Ít truy cập, không critical | Tức thì | Thấp hơn nữa |
| **Glacier Instant** | Archive, truy cập vài lần/tháng | Milliseconds | Rẻ |
| **Glacier Flexible** | Archive, truy cập vài lần/năm | 1-12 giờ | Rẻ hơn |
| **Glacier Deep Archive** | Long-term archive | 12-48 giờ | Rẻ nhất |
| **Intelligent-Tiering** | Pattern không đoán được | Tự động | Tự tối ưu |

**S3 Lifecycle Policy:** Tự động chuyển object sang class rẻ hơn sau X ngày.

---

## 4. IAM Role vs IAM User vs IAM Policy - phân biệt và khi nào dùng?

| | IAM User | IAM Role | IAM Policy |
|-|----------|----------|------------|
| Là gì | Người dùng cụ thể | Danh tính tạm thời | Tập hợp quyền |
| Credentials | Access key / Password | Temporary credentials | Không (đính vào entity khác) |
| Dùng cho | Con người (dev, admin) | AWS services, cross-account | Gắn vào User/Role/Group |

**Khi nào dùng gì:**

- **IAM User:** Lập trình viên cần access AWS console/CLI
- **IAM Role:** EC2 instance cần đọc S3, Lambda cần ghi DynamoDB, CI/CD pipeline...
- **IAM Policy:** Định nghĩa quyền (allow/deny action trên resource)

**Best practice:**
- **Không dùng root account** cho việc thường ngày
- **Không hardcode** Access Key trong code → dùng IAM Role
- **Principle of Least Privilege:** Chỉ cấp quyền tối thiểu cần thiết

```json
// Ví dụ IAM Policy cho phép đọc S3 bucket cụ thể
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:GetObject", "s3:ListBucket"],
    "Resource": ["arn:aws:s3:::my-bucket", "arn:aws:s3:::my-bucket/*"]
  }]
}
```

---

## 5. Security Group hoạt động như thế nào (stateful)?

Security Group là **virtual firewall** cho EC2 instance.

**Stateful** = Nếu cho phép traffic vào, response traffic tự động được phép ra (và ngược lại).

```
Ví dụ:
- Inbound rule: Allow TCP port 80 from 0.0.0.0/0
- Request vào port 80 → được phép
- Response từ server ra → TỰ ĐỘNG được phép (dù không có outbound rule cho port đó)
```

**Default behavior:**
- **Inbound:** Block tất cả (deny all)
- **Outbound:** Allow tất cả

**Một instance có thể gắn nhiều Security Group.** Các rule được **OR** với nhau (union).

**Thực tế trong dự án NoteMesh:**
```
ALB Security Group:
  Inbound: 80, 443 from 0.0.0.0/0
  
App EC2 Security Group:
  Inbound: 8080 from ALB Security Group (không phải từ internet!)
  
RDS Security Group:
  Inbound: 5432 from App EC2 Security Group
```

---

## 6. RDS là gì? Lợi ích so với tự cài DB trên EC2?

**RDS (Relational Database Service):** Managed database service của AWS, hỗ trợ PostgreSQL, MySQL, MariaDB, Oracle, SQL Server, Aurora.

| | RDS | Tự cài DB trên EC2 |
|-|-----|-------------------|
| Patching | AWS tự làm | Tự quản lý |
| Backup | Tự động (Point-in-time restore) | Tự script |
| Failover | Multi-AZ tự động | Tự cấu hình |
| Scaling | Click button | Tự làm |
| Monitoring | CloudWatch tích hợp | Tự setup |
| Chi phí | Cao hơn | Thấp hơn nhưng tốn engineering time |

**Multi-AZ RDS:** Primary ở AZ-1, Standby ở AZ-2. Failover tự động ~60-120 giây nếu primary down.

**Read Replica:** Replica chỉ đọc, giảm tải cho primary. Có thể ở Region khác (cross-region).

---

## 7. CloudFront là gì? Lợi ích khi kết hợp với S3?

**CloudFront** là CDN (Content Delivery Network) của AWS với 450+ edge locations toàn cầu.

**Cách hoạt động:**
```
User (Việt Nam) → CloudFront Edge (Singapore) → S3 Bucket (us-east-1)
                                    ↑ Cache hit → trả về ngay
```

**Lợi ích kết hợp với S3:**
1. **Giảm latency:** Serve file từ edge gần user nhất
2. **Bảo mật:** Ẩn S3 bucket, không expose trực tiếp (dùng OAC)
3. **Tiết kiệm chi phí:** S3 data transfer tốn tiền, CloudFront rẻ hơn
4. **HTTPS:** CloudFront hỗ trợ SSL/TLS miễn phí
5. **DDoS protection:** AWS Shield tích hợp sẵn

**OAC (Origin Access Control):** Chỉ cho phép CloudFront đọc S3, chặn direct access.

---

## 8. ALB vs NLB khác nhau thế nào?

| | ALB (Application LB) | NLB (Network LB) |
|-|----------------------|------------------|
| Tầng OSI | Layer 7 (HTTP/HTTPS) | Layer 4 (TCP/UDP) |
| Routing | URL path, hostname, header, query | IP + Port |
| Protocol | HTTP, HTTPS, WebSocket | TCP, UDP, TLS |
| Static IP | Không (dùng DNS) | Có (Elastic IP) |
| Latency | Cao hơn | Cực thấp (ultra-low) |
| Use case | Web apps, microservices, REST API | Gaming, IoT, Financial, VoIP |
| Health check | HTTP/HTTPS | TCP/HTTP |

**ALB Host-based routing** (dùng trong NoteMesh):
```
api.notemesh.com    → Target Group: App EC2
jenkins.notemesh.com → Target Group: Jenkins EC2
notemesh.com        → Target Group: Frontend
```

---

## 9. Auto Scaling Group là gì? Khi nào cần dùng?

**ASG (Auto Scaling Group)** tự động thêm/xóa EC2 instance dựa trên metrics.

**Thành phần:**
- **Launch Template:** Cấu hình instance (AMI, instance type, SG, user data...)
- **Min/Max/Desired capacity:** Giới hạn số instance
- **Scaling Policy:** Điều kiện scale

**Scaling Policies:**
- **Target Tracking:** Giữ CPU ở mức 70% → tự thêm/xóa instance
- **Step Scaling:** CPU > 80% → thêm 2 instance; CPU > 90% → thêm 5 instance
- **Scheduled:** Scale theo lịch (8AM-10PM nhiều instance hơn)

**Khi nào dùng:**
- Workload không đều (buổi sáng ít, buổi tối nhiều)
- Cần HA (replace instance bị chết tự động)
- Muốn tiết kiệm chi phí (scale down khi nhàn)

---

## 10. VPC Peering và VPN Gateway là gì?

**VPC Peering:** Kết nối 2 VPC với nhau như thể cùng một network. Traffic đi qua AWS backbone (không ra internet).

```
VPC A (10.0.0.0/16) ←→ VPC Peering ←→ VPC B (172.16.0.0/16)
```

**Giới hạn:** Không transitive (A-B, B-C, nhưng A không nói chuyện được với C qua B).

**VPN Gateway:** Kết nối on-premises (văn phòng, data center) với AWS VPC qua Internet sử dụng IPsec VPN.

```
Văn phòng ←→ Customer Gateway ←→ VPN Tunnel ←→ AWS VPN Gateway ←→ VPC
```

**AWS Direct Connect:** Kết nối vật lý dedicated (không qua internet), băng thông cao, latency thấp, ổn định hơn VPN.

| | VPC Peering | VPN Gateway | Direct Connect |
|-|-------------|-------------|----------------|
| Kết nối | VPC-VPC | On-prem-VPC | On-prem-VPC |
| Qua Internet | Không | Có (mã hóa) | Không |
| Latency | Thấp | Cao hơn | Thấp, ổn định |
| Chi phí | Thấp | Trung bình | Cao |
