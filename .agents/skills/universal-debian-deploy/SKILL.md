---
name: universal-debian-deploy
description: Universal production deployment, server provisioning, process supervision, reverse proxying, and database setup guide for ANY programming language or tech stack on Linux/Debian/Ubuntu VPS.
---

# Universal Linux VPS Deployment Skill (Any Tech Stack)

This skill provides architecture patterns, deployment blueprints, and operational runbooks for **ANY** technology stack on a Debian/Ubuntu Linux VPS.

---

## 1. The Universal Web Service Architecture Model

Regardless of language or framework, virtually every production web application on Linux falls into one of **5 Execution Categories**:

```
Internet (HTTP/HTTPS: 80/443)
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. Ingress / Reverse Proxy (Nginx, Caddy, or Cloudflare)    │
│    • SSL Termination (Let's Encrypt / Auto-HTTPS)           │
│    • Static Asset Serving & Gzip/Brotli Compression         │
└──────────────┬──────────────────────────────┬───────────────┘
               │ (Proxy to internal port / unix socket)
               ▼                              ▼
┌──────────────────────────────┐ ┌────────────────────────────┐
│ 2. Process Supervised App    │ │ 3. Containerized Stack     │
│    (Managed by systemd)      │ │    (Docker Compose/Podman) │
│    • Go, Rust, C++, Zig      │ │    • Multi-container apps  │
│    • Node, Bun, Deno         │ │    • Isolated environments │
│    • Python, PHP, Ruby       │ └────────────────────────────┘
│    • Java/JVM, .NET Core     │
│    • Elixir/Phoenix          │
└──────────────┬───────────────┘
               │ (TCP / Socket)
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Persistence Layer (PostgreSQL, MySQL, SQLite, Redis, etc)│
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Stack-Agnostic Execution Blueprints

Select the pattern that matches your project:

### Pattern A: Compiled Binary (Go, Rust, C++, Zig, Swift)
- **Characteristics:** Single standalone executable, zero runtime dependencies, ultra-low memory.
- **Build:** Compile on CI/CD or local build step (`cargo build --release`, `go build -o app .`).
- **Run:** Direct systemd execution of the binary binary file.
- **systemd ExecStart:** `ExecStart=/var/www/app/app-binary`

### Pattern B: Managed Runtime / JVM (Java, Spring Boot, Kotlin, .NET Core, C#)
- **Characteristics:** Runs atop a virtual machine (JVM or .NET CLR).
- **Runners:** OpenJDK (`java -jar app.jar`) or `dotnet App.dll`.
- **systemd ExecStart:**
  - Java: `ExecStart=/usr/bin/java -Xmx1024m -jar /var/www/app/app.jar --spring.profiles.active=prod`
  - .NET: `ExecStart=/usr/bin/dotnet /var/www/app/App.dll`

### Pattern C: Dynamic / Scripted Runtime (Node.js, Bun, Deno, Python, Ruby, Elixir)
- **Node/Bun/Deno:**
  - `ExecStart=/usr/bin/node /var/www/app/server.js` or `/usr/local/bin/bun run start`
- **Python (FastAPI, Flask, Django):**
  - Use Gunicorn + Uvicorn workers in a dedicated virtualenv (`venv`).
  - `ExecStart=/var/www/app/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 127.0.0.1:8000`
- **Ruby (Rails):**
  - Use Puma: `ExecStart=/usr/local/bin/bundle exec puma -C config/puma.rb`
- **PHP (Laravel, Symfony, WordPress):**
  - Use `php-fpm` (FastCGI Process Manager) proxied by Nginx via fastcgi_pass unix socket `/run/php/php-fpm.sock`.

### Pattern D: Containerized (Docker & Docker Compose)
- **Characteristics:** Works identically across any language without installing local runtimes.
- **Workflow:**
  ```bash
  # Start or update any containerized project
  docker compose pull && docker compose up -d --remove-orphans
  ```
- **Managed by systemd (Optional for auto-boot):**
  ```ini
  [Service]
  WorkingDirectory=/var/www/app
  ExecStart=/usr/bin/docker compose up
  ExecStop=/usr/bin/docker compose down
  ```

### Pattern E: Static Client-Side SPA (React, Vue, Svelte, Angular, Astro, HTML)
- No application server required!
- Build static bundle (`dist/` or `out/`) and serve directly via Nginx or Caddy with HTML5 client-side routing fallback: `try_files $uri $uri/ /index.html;`.

---

## 3. Universal Process Supervision (systemd)

For any non-containerized stack, use this universal systemd template at `/etc/systemd/system/<app-name>.service`:

```ini
[Unit]
Description=<App Name> Production Service
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/<app-name>
EnvironmentFile=/var/www/<app-name>/.env

# Replace this line with your stack's specific start command:
ExecStart=<PATH_TO_RUNNER_OR_BINARY>

# Universal Resilience
Restart=always
RestartSec=3s
LimitNOFILE=65535

# Standard Security Hardening
PrivateTmp=true
ProtectSystem=full
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

---

## 4. Ingress & Reverse Proxy Options

### Option 1: Nginx (Industry Standard)
Reverse-proxies any upstream TCP port (`127.0.0.1:<PORT>`) or Unix domain socket (`unix:/run/app.sock`):
```nginx
server {
    listen 80;
    server_name example.com;

    location / {
        proxy_pass http://127.0.0.1:3000; # Any backend port
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Option 2: Caddy (Zero-Config Automatic SSL)
If you want automatic HTTPS with zero Certbot commands:
```caddy
example.com {
    reverse_proxy 127.0.0.1:3000
}
```

---

## 5. Universal Database Options

- **PostgreSQL:** `sudo apt install -y postgresql` (Relational, JSONB, heavy transactions)
- **MySQL / MariaDB:** `sudo apt install -y mariadb-server` (Standard relational, PHP/Laravel, Java)
- **SQLite:** Zero setup, file-based embedded DB (PocketBase, LiteFS, low-concurrency apps)
- **Redis / Valkey:** `sudo apt install -y redis-server` (Caching, queues, pub/sub, session state)
- **MongoDB:** NoSQL document database

---

## 6. The Universal 4-Step Deployment Checklist for ANY Stack

1. **Provision Dependencies & User:** Create `www-data` or dedicated service user with least privileges.
2. **Environment & Secrets:** Secure `.env` with `chmod 600 /var/www/<app>/.env` owned by `www-data`.
3. **Supervisor / Lifecycle:** Configure systemd unit or Docker Compose for automatic restart on crash/reboot.
4. **Health Check Endpoint:** Always include `/healthz` or `/health` returning `200 OK` to verify zero-downtime updates:
   ```bash
   curl -sf http://127.0.0.1:<PORT>/healthz || exit 1
   ```
