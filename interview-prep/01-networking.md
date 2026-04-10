# 🌐 Networking & Hệ thống cơ bản

---

## 1. OSI Model có mấy tầng? Giải thích từng tầng.

OSI Model có **7 tầng**, từ dưới lên:

| Tầng | Tên | Chức năng | Ví dụ |
|------|-----|-----------|-------|
| 7 | Application | Giao tiếp với ứng dụng người dùng | HTTP, FTP, DNS, SMTP |
| 6 | Presentation | Mã hóa, nén, chuyển đổi định dạng dữ liệu | SSL/TLS, JPEG, UTF-8 |
| 5 | Session | Quản lý phiên kết nối (mở, đóng, đồng bộ) | NetBIOS, RPC |
| 4 | Transport | Truyền dữ liệu end-to-end, kiểm soát lỗi | TCP, UDP |
| 3 | Network | Định tuyến gói tin giữa các mạng | IP, ICMP, Router |
| 2 | Data Link | Truyền frame trong cùng một mạng | Ethernet, MAC, Switch |
| 1 | Physical | Tín hiệu vật lý (điện, quang, sóng) | Cáp đồng, Fiber, Hub |

> **Mẹo nhớ:** "**A**ll **P**eople **S**eem **T**o **N**eed **D**ata **P**rocessing"

---

## 2. Phân biệt TCP và UDP. Khi nào dùng cái nào?

| Đặc điểm | TCP | UDP |
|----------|-----|-----|
| Kết nối | Connection-oriented (3-way handshake) | Connectionless |
| Độ tin cậy | Đảm bảo gói tin đến đủ, đúng thứ tự | Không đảm bảo |
| Tốc độ | Chậm hơn (overhead) | Nhanh hơn |
| Kiểm soát lỗi | Có (ACK, retransmit) | Không |
| Flow control | Có | Không |

**Dùng TCP khi:** cần độ chính xác cao — HTTP/HTTPS, SSH, FTP, email, database.

**Dùng UDP khi:** cần tốc độ, chấp nhận mất gói — video streaming, VoIP, DNS, game online, WebRTC.

```
TCP 3-way handshake:
Client → SYN → Server
Client ← SYN-ACK ← Server
Client → ACK → Server
(Kết nối được thiết lập)
```

---

## 3. DNS hoạt động như thế nào? Giải thích quá trình resolve một domain.

DNS (Domain Name System) dịch tên miền → địa chỉ IP.

**Quá trình resolve `www.example.com`:**

```
1. Browser kiểm tra cache local
2. OS kiểm tra file /etc/hosts
3. Hỏi Recursive Resolver (thường là DNS của ISP)
4. Recursive Resolver hỏi Root Name Server (biết .com ở đâu)
5. Hỏi TLD Name Server (.com) → trả về Authoritative NS của example.com
6. Hỏi Authoritative Name Server của example.com → trả về IP
7. Recursive Resolver cache kết quả và trả về browser
```

**Các record DNS phổ biến:**
- `A` — domain → IPv4
- `AAAA` — domain → IPv6
- `CNAME` — alias (domain → domain khác)
- `MX` — mail server
- `TXT` — xác minh, SPF, DKIM
- `NS` — name server

**TTL (Time To Live):** Thời gian cache DNS. TTL thấp → update nhanh hơn nhưng tốn query nhiều hơn.

---

## 4. HTTP vs HTTPS khác nhau điểm gì? TLS handshake hoạt động ra sao?

| | HTTP | HTTPS |
|-|------|-------|
| Cổng | 80 | 443 |
| Mã hóa | Không | Có (TLS/SSL) |
| Bảo mật | Dữ liệu plain text | Dữ liệu được mã hóa |
| Certificate | Không cần | Cần SSL certificate |

**TLS Handshake (TLS 1.3 đơn giản hóa):**

```
1. Client Hello: Gửi TLS version, cipher suites, random number
2. Server Hello: Chọn cipher suite, gửi certificate (chứa public key)
3. Client xác minh certificate với CA (Certificate Authority)
4. Key Exchange: Tạo session key chung (dùng asymmetric crypto)
5. Finished: Cả 2 bên xác nhận, bắt đầu giao tiếp bằng symmetric key
```

> **Asymmetric** (RSA/ECDH) dùng để trao đổi key ban đầu.  
> **Symmetric** (AES) dùng để encrypt data sau khi kết nối.

---

## 5. Load Balancer là gì? Phân biệt L4 vs L7 Load Balancer.

**Load Balancer** phân phối traffic đến nhiều server backend để tránh quá tải một server.

| | L4 (Transport Layer) | L7 (Application Layer) |
|-|---------------------|------------------------|
| Tầng OSI | 4 (TCP/UDP) | 7 (HTTP/HTTPS) |
| Nhìn vào | IP + Port | URL, Header, Cookie, Host |
| Ví dụ AWS | NLB (Network Load Balancer) | ALB (Application Load Balancer) |
| Tốc độ | Nhanh hơn | Chậm hơn (phân tích sâu hơn) |
| Use case | TCP apps, gaming, low-latency | Web apps, microservices, host-based routing |

**Routing algorithms:**
- **Round Robin:** Lần lượt từng server
- **Least Connections:** Server ít kết nối nhất
- **IP Hash:** Cùng IP → cùng server (sticky session)

---

## 6. NAT là gì? Dùng để làm gì trong cloud networking?

**NAT (Network Address Translation)** chuyển đổi địa chỉ IP private → public khi truy cập internet.

**Trong AWS:**
- **NAT Gateway** đặt ở Public Subnet
- Instance ở **Private Subnet** muốn ra internet → đi qua NAT Gateway
- NAT Gateway có Elastic IP (public IP cố định)
- Traffic chiều vào từ internet **không thể** trực tiếp đến Private Subnet

```
Private EC2 → NAT Gateway (Public Subnet) → Internet Gateway → Internet
```

**Tại sao cần NAT?**
- Database, internal services nên ở Private Subnet (không expose ra internet)
- Nhưng vẫn cần download packages, update OS → cần NAT

---

## 7. Phân biệt Public Subnet và Private Subnet trong VPC.

| | Public Subnet | Private Subnet |
|-|---------------|----------------|
| Internet Gateway | Có route đến IGW | Không có route đến IGW |
| Public IP | Instance có thể có Public IP | Không có Public IP |
| Truy cập từ internet | Trực tiếp | Không thể (phải qua LB/Bastion) |
| Use case | Web servers, ALB, NAT Gateway | Database, App servers, Cache |

**Kiến trúc điển hình:**
```
Internet
    ↓
Internet Gateway
    ↓
Public Subnet: ALB, NAT Gateway
    ↓
Private Subnet: EC2 App, RDS
```

---

## 8. CIDR notation là gì? /24 có bao nhiêu IP?

**CIDR (Classless Inter-Domain Routing)** biểu diễn network address và subnet mask.

Format: `IP/prefix-length`

Ví dụ: `10.0.1.0/24`

| CIDR | Subnet Mask | Số IP | Usable IP |
|------|-------------|-------|-----------|
| /32  | 255.255.255.255 | 1 | 1 (host) |
| /24  | 255.255.255.0 | 256 | 254 |
| /16  | 255.255.0.0 | 65,536 | 65,534 |
| /8   | 255.0.0.0 | 16,777,216 | nhiều |

**`/24` = 256 IP, trừ 2 (network + broadcast) = 254 usable IPs.**

Trong AWS, mỗi subnet còn bị trừ thêm 5 IP (AWS reserved), nên `/24` còn 251 IPs.

---

## 9. Firewall vs Security Group vs NACL khác nhau thế nào?

| | Security Group | NACL |
|-|---------------|------|
| Áp dụng cho | Instance (ENI level) | Subnet level |
| Stateful/Stateless | **Stateful** | **Stateless** |
| Rules | Chỉ Allow | Allow và Deny |
| Return traffic | Tự động cho phép | Phải tạo rule explicit |
| Thứ tự rule | Tất cả rules được evaluate | Theo số thứ tự (thấp trước) |

**Stateful vs Stateless:**
- **Stateful (SG):** Cho phép inbound HTTP → outbound response tự động được phép.
- **Stateless (NACL):** Phải tạo cả inbound lẫn outbound rule.

**Best practice:**
- Dùng **Security Group** làm firewall chính.
- Dùng **NACL** để block IP cụ thể ở subnet level (defense in depth).
