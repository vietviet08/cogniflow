# 🛠️ Linux & Shell

---

## 1. Các lệnh thường dùng để debug

### Process & Resource

```bash
# Xem process đang chạy (real-time)
top                    # Cơ bản
htop                   # Đẹp hơn, cần cài: apt install htop
ps aux                 # Liệt kê tất cả processes
ps aux | grep nginx    # Tìm process nginx
kill -9 <PID>          # Force kill process
```

### Disk Usage

```bash
df -h                  # Disk space của filesystem (human readable)
df -h /                # Disk space của partition root
du -sh /var/log        # Tổng dung lượng folder /var/log
du -sh * | sort -rh    # Sắp xếp folder theo dung lượng giảm dần
du -sh /var/log/* | sort -rh | head -20  # Top 20 file lớn nhất
```

### Network

```bash
# Kiểm tra kết nối
ping google.com
ping -c 4 8.8.8.8      # Ping 4 lần rồi dừng

# Trace route (debug latency)
traceroute google.com
mtr google.com         # Real-time traceroute

# Xem port đang lắng nghe
netstat -tlnp          # t=tcp, l=listen, n=numeric, p=process
ss -tlnp               # Tương tự netstat, nhanh hơn

# Test HTTP endpoint
curl -I https://api.notemesh.com/health      # Chỉ xem header
curl -v https://api.notemesh.com/users        # Verbose (debug)
curl -w "%{time_total}\n" https://api.notemesh.com  # Xem response time

# DNS lookup
nslookup notemesh.com
dig notemesh.com
dig +short notemesh.com A
```

### Log Analysis

```bash
# Xem log real-time
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
journalctl -f -u nginx          # SystemD service log

# Xem log với filter
grep "ERROR" /var/log/app.log
grep "ERROR\|WARN" /var/log/app.log   # Multiple patterns
grep -i "error" /var/log/app.log      # Case insensitive

# Xem N dòng cuối
tail -n 100 /var/log/app.log
tail -100 /var/log/app.log

# Docker container logs
docker logs notemesh-api -f --tail 100
```

---

## 2. Permission trong Linux: `chmod 755` nghĩa là gì?

**Permission format:** `rwxrwxrwx`

- `r` = read = 4
- `w` = write = 2
- `x` = execute = 1
- `-` = no permission = 0

**Octal notation:**

```
chmod 755 file

7 = 4+2+1 = rwx  → Owner: read + write + execute
5 = 4+0+1 = r-x  → Group: read + execute (no write)
5 = 4+0+1 = r-x  → Others: read + execute (no write)
```

**Các giá trị phổ biến:**

| Octal | Symbolic | Mô tả | Dùng cho |
|-------|---------|-------|----------|
| `755` | `rwxr-xr-x` | Owner full, others r+x | Scripts, directories |
| `644` | `rw-r--r--` | Owner r+w, others read only | Config files |
| `600` | `rw-------` | Chỉ owner r+w | SSH private key |
| `400` | `r--------` | Read only (even owner) | AWS .pem key |
| `777` | `rwxrwxrwx` | Full cho tất cả | ❌ Không dùng production |

```bash
# Thay đổi permission
chmod 755 script.sh
chmod +x script.sh        # Thêm execute
chmod -w config.conf      # Bỏ write cho tất cả
chmod -R 755 /var/www/    # Recursive (-R)

# Thay đổi owner
chown ubuntu:ubuntu file.txt        # user:group
chown -R ubuntu:ubuntu /app/        # Recursive
```

---

## 3. `systemctl` dùng để làm gì?

**systemctl** quản lý systemd services (init system của modern Linux).

```bash
# Quản lý service
systemctl start nginx          # Khởi động nginx
systemctl stop nginx           # Dừng nginx
systemctl restart nginx        # Restart nginx
systemctl reload nginx         # Reload config (không kill process)
systemctl status nginx         # Xem trạng thái

# Boot behavior
systemctl enable nginx         # Tự start khi server boot
systemctl disable nginx        # Không auto start
systemctl is-enabled nginx     # Kiểm tra có enabled không

# Xem log của service
journalctl -u nginx            # Tất cả log
journalctl -u nginx -f         # Real-time log
journalctl -u nginx --since "1 hour ago"

# Xem tất cả services
systemctl list-units --type=service
systemctl list-units --type=service --state=running
```

---

## 4. `grep`, `awk`, `sed` - phân biệt use case

### `grep` - Tìm kiếm text

```bash
# Cơ bản
grep "ERROR" app.log
grep -n "ERROR" app.log          # Kèm số dòng
grep -i "error" app.log          # Ignore case
grep -v "DEBUG" app.log          # Inverse (loại trừ)
grep -c "ERROR" app.log          # Đếm số dòng match
grep -r "TODO" ./src/            # Recursive search

# Regex
grep -E "ERROR|WARN" app.log     # Extended regex
grep "^2024" app.log             # Bắt đầu bằng 2024
grep "\.py$" app.log             # Kết thúc bằng .py

# Kết hợp
cat /var/log/nginx/access.log | grep "POST" | grep "500"
```

### `awk` - Xử lý và extract fields

```bash
# Syntax: awk '{action}' file
# $1, $2... là các fields (mặc định split bởi space)

# In field thứ 1 (IP address trong access.log)
awk '{print $1}' /var/log/nginx/access.log

# In field 1 và 7 (IP và status code)
awk '{print $1, $9}' /var/log/nginx/access.log

# Lọc dòng, chỉ in HTTP 500 errors
awk '$9 == 500 {print $0}' /var/log/nginx/access.log

# Custom delimiter (CSV)
awk -F',' '{print $1}' data.csv

# Tính tổng (summing)
awk '{sum += $10} END {print "Total bytes:", sum}' access.log

# Đếm occurrences
awk '{count[$1]++} END {for (ip in count) print ip, count[ip]}' access.log
```

### `sed` - Stream Editor, tìm và thay thế

```bash
# Syntax: sed 's/pattern/replacement/flags' file

# Thay thế text (in ra stdout, không sửa file)
sed 's/localhost/production.server.com/' config.conf

# Thay thế IN FILE (-i)
sed -i 's/localhost/production.server.com/' config.conf

# Thay thế tất cả occurrences trong dòng (g flag)
sed 's/foo/bar/g' file.txt

# Xóa dòng trống
sed '/^$/d' file.txt

# Xóa comments và dòng trống
sed '/^#/d; /^$/d' nginx.conf

# Thay thế nhiều patterns
sed -e 's/foo/bar/g' -e 's/baz/qux/g' file.txt

# In dòng từ 10 đến 20
sed -n '10,20p' file.txt

# Thêm dòng sau dòng match
sed '/^server {/a\    listen 443 ssl;' nginx.conf
```

---

## 5. Cách xem log real-time

```bash
# Plain log file
tail -f /var/log/nginx/access.log
tail -f /var/log/app/app.log

# Nhiều file cùng lúc
tail -f /var/log/nginx/access.log /var/log/nginx/error.log

# Kết hợp filter
tail -f /var/log/app.log | grep --line-buffered "ERROR"

# SystemD service
journalctl -f -u nginx
journalctl -f -u docker
journalctl -f -u notemesh-api

# Docker container
docker logs notemesh-api -f
docker logs notemesh-api -f --tail 100   # Bắt đầu từ 100 dòng cuối

# Docker Compose
docker compose logs -f
docker compose logs -f api               # Chỉ service api
```

---

## 6. Viết bash script kiểm tra service có đang chạy không

```bash
#!/bin/bash
# check_service.sh - Kiểm tra service có đang chạy không

SERVICE_NAME="${1:-nginx}"  # Tham số đầu vào, mặc định là nginx

check_service() {
    local service=$1

    # Cách 1: Dùng systemctl
    if systemctl is-active --quiet "$service"; then
        echo "✅ Service '$service' is running"
        return 0
    else
        echo "❌ Service '$service' is NOT running"
        return 1
    fi
}

check_port() {
    local host=$1
    local port=$2

    # Cách 2: Kiểm tra port
    if nc -z "$host" "$port" 2>/dev/null; then
        echo "✅ Port $port on $host is open"
    else
        echo "❌ Port $port on $host is CLOSED"
    fi
}

check_http() {
    local url=$1

    # Cách 3: HTTP health check
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$url")
    if [ "$HTTP_CODE" -eq 200 ]; then
        echo "✅ $url returned HTTP $HTTP_CODE"
    else
        echo "❌ $url returned HTTP $HTTP_CODE"
    fi
}

# Main script
echo "=== Service Check Report ==="
echo "Time: $(date)"
echo ""

check_service "$SERVICE_NAME"

echo ""
echo "=== Port Checks ==="
check_port "localhost" 80
check_port "localhost" 443
check_port "localhost" 5432

echo ""
echo "=== HTTP Health Checks ==="
check_http "http://localhost/health"

# Auto-restart nếu service down
if ! systemctl is-active --quiet "$SERVICE_NAME"; then
    echo ""
    echo "⚠️  Attempting to restart $SERVICE_NAME..."
    systemctl restart "$SERVICE_NAME"
    sleep 3
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo "✅ Successfully restarted $SERVICE_NAME"
    else
        echo "❌ Failed to restart $SERVICE_NAME"
        exit 1
    fi
fi
```

```bash
# Chạy script
chmod +x check_service.sh
./check_service.sh nginx
./check_service.sh docker
```

**Thực tế:** Script này có thể kết hợp với **cron job**:
```bash
# Crontab - chạy mỗi 5 phút
*/5 * * * * /opt/scripts/check_service.sh nginx >> /var/log/service_check.log 2>&1
```
