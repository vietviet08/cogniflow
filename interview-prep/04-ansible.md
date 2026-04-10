# ⚙️ Configuration Management - Ansible

---

## 1. Ansible là gì? Khác Terraform ở điểm nào?

**Ansible** là công cụ automation mã nguồn mở (Red Hat) dùng để **cấu hình server, deploy ứng dụng, và tự động hóa tác vụ IT**.

**Ansible vs Terraform:**

| | Terraform | Ansible |
|-|-----------|---------|
| Mục đích chính | **Provisioning** infrastructure | **Configuration** server |
| Phong cách | Declarative (mô tả trạng thái mong muốn) | Procedural (từng bước thực hiện) |
| State | Có (state file) | Không có state |
| Agent | Agentless | Agentless |
| Giao tiếp | Cloud APIs | SSH (Linux), WinRM (Windows) |
| Ngôn ngữ | HCL | YAML |
| Use case | Tạo VPC, EC2, RDS, S3... | Cài Docker, cấu hình Nginx, deploy app... |

**Workflow điển hình:**
```
Terraform → Tạo EC2 instance (infrastructure)
Ansible   → Cài Docker, cấu hình app trên EC2 đó (configuration)
```

---

## 2. Inventory file là gì?

**Inventory** định nghĩa danh sách servers mà Ansible sẽ quản lý.

**Static Inventory (INI format):**
```ini
# inventory/hosts.ini

[app_servers]
app01 ansible_host=54.123.45.67 ansible_user=ubuntu
app02 ansible_host=54.123.45.68 ansible_user=ubuntu

[jenkins_servers]
jenkins01 ansible_host=54.123.45.69 ansible_user=ubuntu

[all:vars]
ansible_ssh_private_key_file=~/.ssh/notemesh-key.pem
ansible_python_interpreter=/usr/bin/python3
```

**Static Inventory (YAML format):**
```yaml
all:
  children:
    app_servers:
      hosts:
        app01:
          ansible_host: 54.123.45.67
    jenkins_servers:
      hosts:
        jenkins01:
          ansible_host: 54.123.45.69
```

**Dynamic Inventory:** Tự động lấy danh sách EC2 từ AWS (dùng khi instance IP thay đổi thường xuyên):
```bash
ansible-inventory -i aws_ec2.yaml --list
```

---

## 3. Playbook, Role, Task - phân biệt

**Task:** Đơn vị nhỏ nhất - một hành động cụ thể

```yaml
- name: Install Docker
  apt:
    name: docker.io
    state: present
    update_cache: yes
```

**Playbook:** File YAML chứa một hoặc nhiều "plays" - định nghĩa task nào chạy trên host nào

```yaml
# deploy_app.yml
---
- name: Configure App Servers
  hosts: app_servers
  become: yes

  tasks:
    - name: Install Docker
      apt:
        name: docker.io
        state: present

    - name: Start Docker service
      service:
        name: docker
        state: started
        enabled: yes
```

**Role:** Cấu trúc thư mục chuẩn để tổ chức tasks, templates, files, handlers theo chức năng

```
roles/
└── docker/
    ├── tasks/
    │   └── main.yml      # Tasks chính
    ├── handlers/
    │   └── main.yml      # Handlers
    ├── templates/
    │   └── daemon.json.j2  # Jinja2 templates
    ├── files/
    │   └── docker.conf   # Static files
    ├── vars/
    │   └── main.yml      # Variables (cao priority)
    └── defaults/
        └── main.yml      # Default variables (thấp priority)
```

**Dùng role trong playbook:**
```yaml
- name: Configure servers
  hosts: app_servers
  roles:
    - docker
    - nginx
    - app_server
```

---

## 4. Idempotency trong Ansible nghĩa là gì? Tại sao quan trọng?

**Idempotency:** Chạy playbook nhiều lần cho ra kết quả giống nhau như chạy 1 lần.

**Ví dụ idempotent:**
```yaml
# Chạy lần 1: Cài Docker → OK
# Chạy lần 2: Docker đã có → Skip, không cài lại → OK
- name: Install Docker
  apt:
    name: docker.io
    state: present   # "present" = idempotent
```

**Ví dụ KHÔNG idempotent:**
```yaml
# Chạy lần 1: OK
# Chạy lần 2: File bị duplicate, lỗi
- name: Add line to config
  shell: echo "ServerName localhost" >> /etc/apache2/apache2.conf
```

**Fix bằng module đúng:**
```yaml
- name: Add ServerName to config
  lineinfile:
    path: /etc/apache2/apache2.conf
    line: "ServerName localhost"
    state: present   # Idempotent: chỉ thêm nếu chưa có
```

**Tại sao quan trọng:**
- Chạy playbook nhiều lần khi debug không gây ra side effects
- CI/CD có thể chạy lại khi bị lỗi giữa chừng
- Đảm bảo server luôn ở trạng thái mong muốn (desired state)

---

## 5. Handler trong Ansible dùng để làm gì?

**Handler** là task đặc biệt chỉ chạy khi được **notify** từ task khác, và chỉ chạy **một lần** dù được notify nhiều lần.

**Use case phổ biến:** Restart service sau khi thay đổi config

```yaml
# tasks/main.yml
- name: Update nginx config
  template:
    src: nginx.conf.j2
    dest: /etc/nginx/nginx.conf
  notify: Restart nginx        # Trigger handler

- name: Update nginx SSL cert
  copy:
    src: cert.pem
    dest: /etc/nginx/ssl/cert.pem
  notify: Restart nginx        # Trigger cùng handler

# handlers/main.yml
handlers:
  - name: Restart nginx
    service:
      name: nginx
      state: restarted
    # Chỉ restart 1 lần dù được notify 2 lần ở trên
```

**Lợi ích:** Tránh restart service nhiều lần không cần thiết khi có nhiều thay đổi config.

**Handler chạy khi:** Cuối mỗi play (hoặc dùng `meta: flush_handlers` để chạy ngay).

---

## 6. `ansible_user` và `become` dùng để làm gì?

**`ansible_user`:** User SSH để kết nối vào server

```yaml
# Trong inventory
app01 ansible_host=54.123.45.67 ansible_user=ubuntu

# Hoặc trong group_vars/all.yml
ansible_user: ubuntu
ansible_ssh_private_key_file: ~/.ssh/notemesh-key.pem
```

**`become`:** Privilege escalation - chạy lệnh với quyền cao hơn (thường là root dùng sudo)

```yaml
# Toàn bộ playbook chạy với sudo
- name: Configure servers
  hosts: app_servers
  become: yes          # Tương đương sudo cho tất cả tasks

  tasks:
    - name: Install packages
      apt:
        name: nginx
        state: present   # Cần sudo → become: yes

    # Overide: chạy task này với user cụ thể
    - name: Deploy app code
      git:
        repo: https://github.com/org/app.git
        dest: /home/ubuntu/app
      become_user: ubuntu   # Chạy với user ubuntu, không phải root
```

**become_method:** sudo (mặc định), su, pbrun, pfexec, doas, dzdo...

---

## 7. Vault trong Ansible giải quyết vấn đề gì?

**Ansible Vault** mã hóa files/variables chứa thông tin nhạy cảm (passwords, API keys...) để có thể commit vào git an toàn.

**Encrypt file:**
```bash
# Mã hóa toàn bộ file
ansible-vault encrypt group_vars/all/secrets.yml

# Mã hóa inline value
ansible-vault encrypt_string 'MySecret123' --name 'db_password'
```

**File secrets.yml sau khi encrypt:**
```yaml
$ANSIBLE_VAULT;1.1;AES256
62653737343332366661363...
```

**Decrypt khi chạy playbook:**
```bash
ansible-playbook deploy.yml --ask-vault-pass

# Hoặc dùng password file (CI/CD)
ansible-playbook deploy.yml --vault-password-file .vault_pass
```

**Best practice cho CI/CD:**
```bash
# Lưu vault password vào env variable (GitHub Secrets)
echo "$VAULT_PASSWORD" > .vault_pass
ansible-playbook deploy.yml --vault-password-file .vault_pass
rm -f .vault_pass
```

---

## 8. `when` condition trong task dùng như thế nào?

**`when`** cho phép chạy task có điều kiện (giống `if` statement):

```yaml
tasks:
  # Chỉ chạy trên Ubuntu
  - name: Install nginx (Ubuntu)
    apt:
      name: nginx
      state: present
    when: ansible_distribution == "Ubuntu"

  # Chỉ chạy trên CentOS/RHEL
  - name: Install nginx (CentOS)
    yum:
      name: nginx
      state: present
    when: ansible_distribution == "CentOS"

  # Điều kiện kết hợp
  - name: Configure production settings
    template:
      src: prod.conf.j2
      dest: /etc/app/config.conf
    when:
      - env == "production"
      - ansible_memtotal_mb >= 4096  # RAM >= 4GB

  # Kiểm tra kết quả task trước
  - name: Check if Docker is installed
    command: docker --version
    register: docker_check
    ignore_errors: yes

  - name: Install Docker (if not installed)
    apt:
      name: docker.io
      state: present
    when: docker_check.failed
```

**Facts thường dùng với when:**
- `ansible_os_family` — "Debian", "RedHat"...
- `ansible_distribution` — "Ubuntu", "CentOS"...
- `ansible_distribution_version` — "20.04", "8"...
- `ansible_architecture` — "x86_64", "arm64"...
- `ansible_memtotal_mb` — RAM tổng (MB)
