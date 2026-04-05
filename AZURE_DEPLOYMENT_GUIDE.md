# Kassa Odoo - Azure Deployment Guide

> **Audience**: DevOps Engineers, Infrastructure Teams
> **Scope**: Deploying Kassa custom Odoo module on Azure VM with Docker Compose, Nginx reverse proxy, and internal RabbitMQ/PostgreSQL services

---

## Quick Start - Azure VM Deployment

### Prerequisites
- Azure VM with Docker and Docker Compose installed
- Ubuntu 20.04 LTS or 22.04 LTS recommended
- Nginx installed and configured for reverse proxy
- Git clone of the Kassa repository

### Step 1: Prepare Environment

```bash
# Navigate to project directory
cd /home/azureuser/kassa

# Copy environment template
cp .env.example .env

# Edit with your Azure infrastructure details
nano .env
```

**Required values to update in `.env`:**

```bash
# Database (PostgreSQL on Azure)
POSTGRES_PASSWORD=<YOUR_SECURE_20_CHARACTER_PASSWORD>
DB_HOST=db  # Keep as 'db' for Docker internal networking

# RabbitMQ broker
RABBIT_PASSWORD=<YOUR_SECURE_20_CHARACTER_PASSWORD>
RABBIT_HOST=rabbitmq  # Keep as 'rabbitmq' for Docker internal networking
RABBIT_VHOST=/kassa

# Public domain
ODOO_DOMAIN=kassa.integration-project-2026-groep-2.my.be
```

### Step 2: Start Docker Compose

```bash
# Build and start all services
docker-compose up -d

# Verify all services are running
docker-compose ps

# Watch logs (Ctrl+C to exit)
docker-compose logs -f odoo

# Check service health
docker-compose exec odoo curl -s http://localhost:8069/health
docker-compose exec rabbitmq rabbitmq-diagnostics -q ping
docker-compose exec db pg_isready -U kassa
```

### Step 3: Configure Nginx Reverse Proxy

Create `/etc/nginx/sites-available/kassa.conf`:

```nginx
# Main Odoo application proxy
upstream kassa_odoo {
    server 127.0.0.1:8069;
}

server {
    listen 80;
    server_name kassa.integration-project-2026-groep-2.my.be;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name kassa.integration-project-2026-groep-2.my.be;
    
    # SSL certificate paths (managed by certbot or Azure)
    ssl_certificate /etc/letsencrypt/live/kassa.integration-project-2026-groep-2.my.be/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/kassa.integration-project-2026-groep-2.my.be/privkey.pem;
    
    # Security headers
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Proxy timeout settings
    proxy_connect_timeout 600;
    proxy_send_timeout 600;
    proxy_read_timeout 600;
    send_timeout 600;
    
    # Client body size (for file uploads)
    client_max_body_size 50M;
    
    # Main application proxy
    location / {
        proxy_pass http://kassa_odoo;
        
        # Forward client information
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host $server_name;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # Static files caching
    location ~* ^/web/(css|js|image|content)/ {
        proxy_pass http://kassa_odoo;
        expires 7d;
        add_header Cache-Control "public, max-age=604800";
    }
}

# RabbitMQ Management UI (HTTPS on 15671)
server {
    listen 15671 ssl http2;
    server_name kassa.integration-project-2026-groep-2.my.be;
    
    ssl_certificate /etc/letsencrypt/live/kassa.integration-project-2026-groep-2.my.be/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/kassa.integration-project-2026-groep-2.my.be/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    auth_basic "RabbitMQ Admin";
    auth_basic_user_file /etc/nginx/.htpasswd_rabbitmq;
    
    location / {
        proxy_pass http://127.0.0.1:15672;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/kassa.conf /etc/nginx/sites-enabled/

# Test Nginx configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

### Step 4: Initialize Odoo Database

```bash
# Create initial Odoo database
docker-compose exec odoo odoo \
  --db_host=db \
  --db_user=kassa \
  --db_password=$(grep POSTGRES_PASSWORD .env | cut -d= -f2) \
  --db_name=kassa_db \
  -i base,web --without-demo=all \
  --stop-after-init

# Restart Odoo service
docker-compose restart odoo

# View startup logs
docker-compose logs odoo
```

### Step 5: Install Custom Module

The Kassa POS module is mounted at `/mnt/extra-addons/kassa_pos` inside the container.

In Odoo UI (after database initialization):
1. Enable Developer Mode: Settings → Activate the Developer Mode (top-right menu)
2. Go to Apps → Update App List
3. Search for "Kassa" or "kassa_pos"
4. Install the "Kassa POS" module

### Step 6: Configure RabbitMQ

Create Odoo user in RabbitMQ:
```bash
# Create user
docker-compose exec rabbitmq rabbitmqctl add_user kassa_user <PASSWORD>

# Create virtual host
docker-compose exec rabbitmq rabbitmqctl add_vhost /kassa

# Set permissions
docker-compose exec rabbitmq rabbitmqctl set_permissions -p /kassa kassa_user ".*" ".*" ".*"

# Verify
docker-compose exec rabbitmq rabbitmqctl list_users
docker-compose exec rabbitmq rabbitmqctl list_vhosts
```

Access RabbitMQ Management UI:
- **URL**: https://kassa.integration-project-2026-groep-2.my.be:15671
- **Username/Password**: Use `RABBIT_USER` and `RABBIT_PASSWORD` from `.env`

---

## Azure Infrastructure Context

### Service Discovery

Services communicate using short names within Docker network:

| Service | Port | Internal Address |
|---------|------|------------------|
| Odoo | 8069 | `http://odoo:8069` (internal) |
| RabbitMQ AMQP | 5672 | `amqp://rabbitmq:5672` (internal) |
| RabbitMQ Management | 15672 | `http://rabbitmq:15672` (internal) |
| PostgreSQL | 5432 | `postgresql://db:5432` (internal) |

### External Access

| Service | External URL | Protocol | Notes |
|---------|---|---|---|
| Odoo | `https://kassa.integration-project-2026-groep-2.my.be` | HTTPS/443 | Via Nginx reverse proxy |
| RabbitMQ Mgmt | `https://kassa.integration-project-2026-groep-2.my.be:15671` | HTTPS/15671 | Via Nginx reverse proxy, HTTP Basic Auth |

### Network Flow

```
Client (Browser/API) 
  ↓ (HTTPS)
Internet → Azure VM Public IP
  ↓ (HTTPS port 443, 15671)
Nginx Reverse Proxy (:443, :15671)
  ↓ (HTTP port 8069, 15672)
Docker Bridge Network (kassa-network)
  ↓
Containers (Odoo, RabbitMQ, PostgreSQL, etc.)
```

---

## Environment Variables Summary

### For Odoo Container
```bash
# Database
DB_HOST=db
DB_PORT=5432
POSTGRES_DB=kassa_db
POSTGRES_USER=kassa
POSTGRES_PASSWORD=<SECURE_PASSWORD>

# RabbitMQ
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=kassa_user
RABBITMQ_PASS=<SECURE_PASSWORD>
RABBITMQ_VHOST=/kassa

# Public Access
ODOO_DOMAIN=kassa.integration-project-2026-groep-2.my.be
```

### For POS Receiver Container
```bash
RABBIT_HOST=rabbitmq
RABBIT_PORT=5672
RABBIT_USER=kassa_user
RABBIT_PASSWORD=<SECURE_PASSWORD>
RABBIT_VHOST=/kassa
```

### For Heartbeat Container
```bash
RABBIT_HOST=rabbitmq
RABBIT_PORT=5672
RABBIT_USER=kassa_user
RABBIT_PASSWORD=<SECURE_PASSWORD>
RABBIT_VHOST=/kassa
HEARTBEAT_INTERVAL_SECONDS=5
HEARTBEAT_EXCHANGE=heartbeat.direct
HEARTBEAT_ROUTING_KEY=routing.heartbeat
HEARTBEAT_QUEUE=heartbeat_queue
```

---

## Production Best Practices

### Security
1. **Never use default credentials**
   - RabbitMQ: Change from `guest/guest`
   - PostgreSQL: Use unique passwords per environment
   - Use Azure Key Vault for secrets management

2. **Network isolation**
   - Expose only Odoo port (via Nginx) and RabbitMQ management UI
   - Keep database and AMQP ports internal only
   - Use Azure Network Security Groups to restrict traffic

3. **SSL/TLS Certificates**
   - Use Let's Encrypt with auto-renewal
   - Or managed certificates from Azure
   - Update Nginx configuration with certificate paths

### Monitoring & Logging
```bash
# View container logs
docker-compose logs -f odoo        # Odoo application
docker-compose logs -f rabbitmq    # RabbitMQ broker
docker-compose logs -f db          # PostgreSQL database
docker-compose logs -f pos_receiver # POS message consumer
docker-compose logs -f heartbeat   # Health monitoring

# Clean up old logs
docker-compose logs --tail=100     # Last 100 lines
docker system prune -a             # Remove unused containers/images
```

### Backup & Recovery
```bash
# Backup PostgreSQL
docker-compose exec db pg_dump \
  -U kassa kassa_db > backup_$(date +%Y%m%d).sql

# Backup Odoo filestore
docker cp kassa-odoo:/var/lib/odoo ./odoo_backup_$(date +%Y%m%d)

# Backup RabbitMQ definitions
docker-compose exec rabbitmq rabbitmqctl export_definitions /tmp/rabbitmq_defs.json
docker cp kassa-rabbitmq:/tmp/rabbitmq_defs.json ./

# Restore PostgreSQL
docker-compose exec -T db psql -U kassa kassa_db < backup_*.sql
```

### Performance Tuning
```bash
# Check container resource usage
docker stats

# Adjust RabbitMQ memory
docker-compose exec rabbitmq rabbitmqctl set_vm_memory_high_watermark 0.6

# Check PostgreSQL connections
docker-compose exec db psql -U kassa kassa_db -c "SELECT count(*) FROM pg_stat_activity;"
```

---

## Troubleshooting

### Odoo Cannot Connect to RabbitMQ
```
Error: Connection refused at rabbitmq:5672

Solution:
1. docker-compose exec rabbitmq rabbitmq-diagnostics ping
2. Check RABBIT_HOST and RABBIT_PORT in .env
3. Verify RabbitMQ container is healthy: docker-compose ps
4. Check RabbitMQ logs: docker-compose logs rabbitmq
```

### PostgreSQL Connection Errors
```
Error: FATAL: role "kassa" does not exist

Solution:
1. Recreate database: docker-compose down && docker-compose up -d
2. Verify credentials in .env match actual database
3. Check file permissions on postgres_data volume
4. Restart PostgreSQL: docker-compose restart db
```

### Nginx Proxy Errors (502 Bad Gateway)
```
Error: upstream timed out while connecting to upstream

Solution:
1. Verify Odoo is running: docker-compose logs odoo
2. Check port mapping: docker-compose ps
3. Verify local:8069:8069 mapping in docker-compose.yml
4. Increase proxy timeouts in nginx.conf
5. Check Azure NSG allows traffic to Docker bridge
```

### RabbitMQ Management UI Access Denied
```
Error: 401 Unauthorized at https://kassa.../15671

Solution:
1. Verify credentials: docker-compose exec rabbitmq rabbitmqctl list_users
2. Create user if missing: docker-compose exec rabbitmq rabbitmqctl add_user <user> <pass>
3. Set permissions: docker-compose exec rabbitmq rabbitmqctl set_permissions -p /kassa <user> ".*" ".*" ".*"
4. Clear browser cache or use incognito window
```

---

## Deployment Checklist

### Pre-Deployment
- [ ] Clone repository to Azure VM
- [ ] Install Docker and Docker Compose
- [ ] Configure Azure Network Security Groups
- [ ] Obtain SSL certificate from Let's Encrypt or Azure
- [ ] Reserve static public IP for VM

### Deployment
- [ ] Copy `.env.example` to `.env`
- [ ] Fill in Azure infrastructure details
- [ ] Set strong passwords (min 20 chars)
- [ ] Run `docker-compose up -d`
- [ ] Verify all services healthy: `docker-compose ps`
- [ ] Initialize Odoo database
- [ ] Install Kassa module via Odoo UI
- [ ] Configure Nginx reverse proxy
- [ ] Test Odoo access via HTTPS
- [ ] Test RabbitMQ Management UI

### Post-Deployment
- [ ] Configure backup strategy
- [ ] Set up monitoring and alerts
- [ ] Document access credentials (store in Key Vault)
- [ ] Train team on deployment procedures
- [ ] Create runbooks for common operations
- [ ] Schedule regular security updates

---

## Additional Resources

- [Odoo Documentation](https://www.odoo.com/documentation/17.0/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [Nginx Reverse Proxy Guide](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
- [RabbitMQ Documentation](https://www.rabbitmq.com/documentation.html)
- [PostgreSQL on Docker](https://hub.docker.com/_/postgres)
- [Azure Virtual Machines](https://docs.microsoft.com/en-us/azure/virtual-machines/)

---

## Support & Escalation

For issues or questions:
1. Check logs: `docker-compose logs -f <service>`
2. Review [ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md)
3. Consult Azure infrastructure documentation
4. Contact DevOps team for Azure/infrastructure issues
5. Contact development team for Odoo/module issues
