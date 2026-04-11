# 🐳 Docker & Container

---

## 1. Container khác Virtual Machine như thế nào?

| | Virtual Machine (VM) | Container |
|-|---------------------|-----------|
| Isolation | Full OS isolation (hypervisor) | Process-level isolation (kernel namespaces) |
| Size | GBs (full OS image) | MBs (chỉ app + dependencies) |
| Boot time | Phút | Giây (thậm chí milliseconds) |
| Resource overhead | Cao (mỗi VM có OS riêng) | Thấp (share kernel với host) |
| Portability | Thấp hơn | Cao (chạy mọi nơi có Docker) |
| Security isolation | Mạnh hơn | Yếu hơn (share kernel) |

```
VM Architecture:
┌────────────────────────────────────────┐
│  App A  │  App B  │  App C             │
│  Guest OS│ Guest OS│ Guest OS           │
├──────────────────────────────────────── │
│              Hypervisor                 │
├─────────────────────────────────────────┤
│              Host OS                    │
│              Hardware                   │
└─────────────────────────────────────────┘

Container Architecture:
┌───────────────────────────────────────┐
│  App A  │  App B  │  App C            │
│ Libs/Deps│Libs/Deps│Libs/Deps         │
├───────────────────────────────────────┤
│        Docker Engine (Runtime)        │
├───────────────────────────────────────┤
│              Host OS (shared kernel)  │
│              Hardware                 │
└───────────────────────────────────────┘
```

---

## 2. Giải thích Dockerfile và các instruction phổ biến

**Dockerfile** là file text chứa tập lệnh để build Docker image.

```dockerfile
# Base image - OS hoặc runtime
FROM node:20-alpine

# Metadata
LABEL maintainer="dev@notemesh.com"

# Biến môi trường
ENV NODE_ENV=production
ENV PORT=3000

# Thư mục làm việc trong container
WORKDIR /app

# Copy file package trước để tận dụng layer cache
COPY package*.json ./

# Chạy lệnh khi BUILD image (install dependencies)
RUN npm ci --only=production

# Copy source code
COPY . .

# Build step
RUN npm run build

# Expose port để document (không thực sự mở port)
EXPOSE 3000

# Tạo non-root user để bảo mật
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

# Lệnh chạy khi START container
CMD ["node", "dist/main.js"]
```

**Phân biệt `CMD` vs `ENTRYPOINT`:**

| | CMD | ENTRYPOINT |
|-|-----|------------|
| Mục đích | Default command (có thể override) | Fixed command (khó override) |
| Override | `docker run image other_cmd` | Cần `--entrypoint` flag |

```dockerfile
# Thường kết hợp:
ENTRYPOINT ["node"]    # Binary cố định
CMD ["dist/main.js"]   # Argument mặc định (có thể override)
```

**`RUN` vs `CMD` vs `ENTRYPOINT`:**
- `RUN`: Chạy khi **build image** (tạo layer mới)
- `CMD`: Chạy khi **start container** (default command)
- `ENTRYPOINT`: Chạy khi **start container** (fixed binary)

---

## 3. Docker image vs Docker container?

| | Docker Image | Docker Container |
|-|-------------|-----------------|
| Trạng thái | Static, read-only | Running instance của image |
| Tương tự | Class trong OOP | Object/instance trong OOP |
| Lưu trữ | Image registry (Docker Hub, ECR) | Running trên host |
| Tạo từ | Dockerfile build | `docker run <image>` |

```bash
# Image: blueprint
docker build -t notemesh-api:v1.0 .
docker pull nginx:latest

# Container: running instance từ image
docker run -d -p 8080:3000 --name api notemesh-api:v1.0

# Một image có thể tạo nhiều container
docker run -d -p 8081:3000 --name api-2 notemesh-api:v1.0
```

**Image Layers:**
```
FROM ubuntu:22.04          → Layer 1 (base)
RUN apt-get install nginx  → Layer 2
COPY app/ /var/www/        → Layer 3
```
Mỗi instruction tạo một layer. Layers được cache → build nhanh hơn.

---

## 4. Docker Compose là gì? Giải thích file docker-compose.yml

**Docker Compose** định nghĩa và chạy multi-container applications.

```yaml
# docker-compose.yml
version: '3.8'

services:
  # Service 1: API Backend
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: notemesh-api
    ports:
      - "8080:3000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/notemesh
      - REDIS_URL=redis://redis:6379
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./uploads:/app/uploads
    restart: unless-stopped
    networks:
      - app-network

  # Service 2: Database
  postgres:
    image: postgres:15-alpine
    container_name: notemesh-db
    environment:
      POSTGRES_DB: notemesh
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - app-network

  # Service 3: Cache
  redis:
    image: redis:7-alpine
    container_name: notemesh-redis
    networks:
      - app-network

volumes:
  postgres_data:    # Named volume, persist data

networks:
  app-network:      # Custom network, services giao tiếp qua tên
    driver: bridge
```

```bash
docker compose up -d          # Start tất cả services
docker compose down           # Stop và remove containers
docker compose logs -f api    # Xem logs của service api
docker compose exec api sh    # Shell vào container
```

---

## 5. Docker network có các loại nào?

| Network Driver | Mô tả | Use case |
|---------------|-------|----------|
| **bridge** | Default. Container cùng bridge nói chuyện được, isolated với host | Development, compose |
| **host** | Container share network stack với host | Performance critical, no isolation needed |
| **overlay** | Kết nối container trên nhiều Docker hosts | Docker Swarm, multi-host |
| **none** | Không có network | Isolated batch jobs |
| **macvlan** | Container có MAC address riêng, trông như physical device | Legacy apps cần direct network |

**Bridge network (phổ biến nhất):**
```bash
# Container trong cùng network giao tiếp qua tên
# api container có thể ping "postgres" thay vì IP
docker network create app-network
docker run --network app-network --name postgres postgres:15
docker run --network app-network --name api myapp
# Trong api: connect đến "postgres:5432"
```

---

## 6. Docker volume vs bind mount khác nhau thế nào?

| | Volume | Bind Mount |
|-|--------|-----------|
| Quản lý bởi | Docker | Host OS |
| Location | `/var/lib/docker/volumes/` | Bất kỳ path nào trên host |
| Portability | Cao (Docker quản lý) | Thấp (depends on host path) |
| Performance | Tốt hơn | Tốt trên Linux, kém trên Mac/Win |
| Backup | `docker volume` commands | Trực tiếp từ host |
| Use case | Production data | Development (live reload) |

```bash
# Volume (production - database data)
docker run -v postgres_data:/var/lib/postgresql/data postgres

# Bind mount (development - live code reload)
docker run -v $(pwd)/src:/app/src myapp
```

---

## 7. Container có stateless không? Data trong container bị mất khi nào?

**Container nên được thiết kế stateless** (12-factor app principles).

**Data bị mất khi:**
- `docker rm container` - xóa container
- `docker run` tạo container mới từ image
- Container crash và restart (nếu không dùng volume)

**Data KHÔNG bị mất khi:**
- `docker stop` / `docker start` (container vẫn tồn tại, chỉ stop)
- Container restart với `restart: unless-stopped`

**Giải pháp persist data:**
```bash
# Volume cho database
docker run -v postgres_data:/var/lib/postgresql/data postgres

# External storage (S3, EFS) cho file uploads
# Mount EFS vào EC2, container bind mount từ EFS path
```

---

## 8. Tối ưu image size bằng cách nào?

**Multi-stage build** (quan trọng nhất):
```dockerfile
# Stage 1: Build (có đầy đủ tools)
FROM node:20 AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Production (chỉ runtime)
FROM node:20-alpine AS production
WORKDIR /app
# Chỉ copy artifacts từ stage build
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
EXPOSE 3000
CMD ["node", "dist/main.js"]

# Kết quả: 200MB → 80MB
```

**Các kỹ thuật khác:**
```dockerfile
# 1. Dùng alpine base image
FROM node:20-alpine  # ~7MB thay vì ~1GB

# 2. Combine RUN commands để giảm layers
RUN apt-get update && \
    apt-get install -y curl wget && \
    rm -rf /var/lib/apt/lists/*   # Xóa cache apt

# 3. .dockerignore - không COPY file không cần thiết
# .dockerignore:
node_modules
.git
*.md
tests/
.env
```

**Kiểm tra kích thước layers:**
```bash
docker history myapp:latest
docker image inspect myapp:latest
```
