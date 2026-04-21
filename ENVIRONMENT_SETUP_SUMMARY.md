# Kassa Environment Variables & Documentation - Complete Package

**Status**: ✅ COMPLETE  
**Date**: April 4, 2026  
**Audience**: Senior DevOps Engineer, Infrastructure Teams

---

## 📋 Executive Summary

You now have a **complete, production-ready environment configuration package** for deploying Team Kassa's custom Odoo module on Azure infrastructure with Nginx reverse proxy, RabbitMQ messaging, and PostgreSQL database.

### What Has Been Delivered

Four comprehensive reference documents + enhanced configuration files:

| Document | Purpose | Audience |
|----------|---------|----------|
| **[ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md)** | Complete reference table of env variables + usage guidelines | Dev/DevOps |
| **[docker-compose.production.yml](./docker-compose.production.yml)** | Production-ready compose file with detailed comments | DevOps/Infra |
| **[.env.example](./.env.example)** | Template for .env file with Azure infrastructure defaults | DevOps |
| **[AZURE_DEPLOYMENT_GUIDE.md](./AZURE_DEPLOYMENT_GUIDE.md)** | Step-by-step deployment guide for Azure VM | DevOps |
| **[CODE_EXAMPLES_ENV_VARIABLES.md](./CODE_EXAMPLES_ENV_VARIABLES.md)** | Python code examples for reading env variables | Developers |

---

## 🎯 Quick Start - 5 Minutes

### Step 1: Prepare Environment File
```bash
cp .env.example .env
nano .env  # Edit with your values
```

### Step 2: Update with Azure Infrastructure Details
```bash
# Minimum required changes:
POSTGRES_PASSWORD=<YOUR_SECURE_PASSWORD>
RABBIT_PASSWORD=<YOUR_SECURE_PASSWORD>
DB_HOST=db  # Keep internal, or use Azure PostgreSQL hostname
RABBIT_HOST=rabbitmq  # Keep internal, or use Azure RabbitMQ hostname
ODOO_DOMAIN=kassa.integration-project-2026-groep-2.my.be
```

### Step 3: Deploy
```bash
docker compose -f docker-compose.production.yml up -d --build
docker compose -f docker-compose.production.yml logs -f odoo
```

### Step 4: Configure Nginx
See [AZURE_DEPLOYMENT_GUIDE.md](./AZURE_DEPLOYMENT_GUIDE.md#step-3-configure-nginx-reverse-proxy)

---

## 📚 Key Features Included

### ✅ Environment Variables Table
- **32 environment variables** documented with descriptions
- **Service mapping** showing which services use which variables
- **Azure-specific** values (RabbitMQ on 15671 HTTPS, internal service names)
- **Examples** for local dev, staging, and production

### ✅ Docker Compose Configuration
- **5 services** configured: Odoo, PostgreSQL, RabbitMQ, POS Receiver, Heartbeat
- **Health checks** for each service
- **Volume persistence** for data durability
- **Internal networking** using Docker bridge network
- **Detailed comments** explaining each variable

### ✅ Security Best Practices
- **No hardcoded passwords** in code/compose files
- **Placeholder values** for secrets (`<PASSWORD_HERE>`)
- **Azure Key Vault integration** examples
- **Network isolation** - only Odoo exposed via Nginx
- **HTTPS/TLS** setup for public access

### ✅ Azure Infrastructure Mapping
```
Your Setup:
├── RabbitMQ: Internal service name "rabbitmq", AMQP 5672, Management 15671
├── Database: PostgreSQL "db" service, port 5432
├── Odoo: Internal port 8069, accessed via nginx reverse proxy
└── Domain: kassa.integration-project-2026-groep-2.my.be (via Nginx HTTPS)
```

### ✅ Production Deployment Guide
- Step-by-step instructions for Azure VM
- Nginx reverse proxy configuration (HTTPS + port 15671)
- RabbitMQ management UI setup
- Database initialization
- Monitoring and troubleshooting

### ✅ Code Examples
- Configuration module pattern (reusable across services)
- RabbitMQ connection utilities
- Odoo custom module integration
- POS receiver service implementation
- Validation scripts and entrypoint

---

## 📖 Documentation Map

### For Configuration/Deployment
Start here → **[AZURE_DEPLOYMENT_GUIDE.md](./AZURE_DEPLOYMENT_GUIDE.md)**
- Complete deployment walkthrough
- Nginx configuration for your domain
- Troubleshooting guide
- Backup and recovery procedures

### For Reference
Use → **[ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md)**
- Full variable descriptions
- Service dependency mapping
- Production guidelines
- Validation examples

### For Implementation
Reference → **[CODE_EXAMPLES_ENV_VARIABLES.md](./CODE_EXAMPLES_ENV_VARIABLES.md)**
- How to read env vars in Python
- RabbitMQ connection patterns
- Odoo module integration
- Validation and testing code

### For Docker Setup
Use → **[docker-compose.production.yml](./docker-compose.production.yml)**
- Enhanced version of existing docker-compose.yml
- Production-ready configuration
- Comments explaining every variable
- Nginx reverse proxy reference

### For .env File
Reference → **[.env.example](./.env.example)**
- Complete template with explanations
- Azure-specific examples
- Security checklist
- Different environment configurations

---

## 🔑 Key Configuration Details for Your Infrastructure

### RabbitMQ Setup
- **Internal Service Name**: `rabbitmq`
- **AMQP Port** (for services): `5672`
- **Management UI Port** (internal): `15672`
- **Management UI** (public): `https://kassa.integration-project-2026-groep-2.my.be:15671`
- **Virtual Host**: `/kassa` (production)

### Database Setup
- **Service Name**: `db`
- **Port** (internal): `5432`
- **Database Name**: `kassa_db`
- **User**: Configurable via `POSTGRES_USER`
- **Password**: Required, from `.env` (never hardcoded)

### Odoo Setup
- **Internal Port**: `8069`
- **WebSocket/Longpolling Port**: `8072`
- **Public URL**: `https://kassa.integration-project-2026-groep-2.my.be`
- **Access**: Via Nginx reverse proxy (no direct external access)
- **Domain Variable**: `ODOO_DOMAIN=kassa.integration-project-2026-groep-2.my.be`

### Network Architecture
```
┌─────────────────────────────────────────────────────────┐
│ INTERNET (users accessing via browser)                  │
└────────────────────┬────────────────────────────────────┘
                     │ HTTPS 443 + 15671
                     ↓
┌─────────────────────────────────────────────────────────┐
│ NGINX REVERSE PROXY (kassa.integration-project-2026-    │
│ groep-2.my.be)                                          │
│ Maps to localhost:8069 (Odoo), 8072 (WebSocket), 15672 │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP (internal)
                     ↓
┌──────────────────────────────────────────────────────────┐
│ DOCKER BRIDGE NETWORK (kassa-network)                    │
├──────────────────────────────────────────────────────────┤
│ Service       │ Port  │ Access                           │
├──────────────┼──────────┬─────────────────────────────┤
│ odoo          │ 8069  │ http://odoo:8069 (internal)  │
│ odoo-ws       │ 8072  │ http://odoo:8072 (internal)  │
│ rabbitmq      │ 5672  │ amqp://rabbitmq:5672        │
│ rabbitmq-mgmt │ 15672 │ http://rabbitmq:15672       │
│ db            │ 5432  │ postgresql://db:5432         │
└──────────────────────────────────────────────────────────┘
```

---

## 🚀 Deployment Workflow

### Local Development
```bash
cp .env.example .env
# Use defaults (db, rabbitmq, guest credentials)
docker compose up -d
# Access at http://localhost:8069
```

### Staging Deployment
```bash
cp .env.example .env.staging
# Update with staging values
docker compose --env-file .env.staging up -d
```

### Production Deployment
```bash
# Step 1: Prepare environment file
cp .env.example .env
nano .env  # Edit with secure values

# Step 2: Pull latest code
git pull origin main

# Step 3: Build and deploy
docker compose -f docker-compose.production.yml build
docker compose -f docker-compose.production.yml up -d

# Step 4: Monitor startup
docker compose -f docker-compose.production.yml logs -f odoo

# Step 5: Configure Nginx (if not already done)
# See AZURE_DEPLOYMENT_GUIDE.md
```

---

## ✅ Pre-Deployment Checklist

### Configuration
- [ ] Copied `.env.example` to `.env`
- [ ] Set all `<PASSWORD_HERE>` placeholders with strong passwords
- [ ] Updated `ODOO_DOMAIN` to your subdomain
- [ ] Verified `DB_HOST`, `RABBIT_HOST` for your infrastructure

### Docker
- [ ] Docker and Docker Compose installed on Azure VM
- [ ] Built Docker image: `docker compose -f docker-compose.production.yml build`
- [ ] Started services: `docker compose -f docker-compose.production.yml up -d`
- [ ] All services healthy: `docker compose -f docker-compose.production.yml ps`

### Networking
- [ ] Azure NSG allows HTTP 80 and HTTPS 443
- [ ] DNS points subdomain to VM IP
- [ ] Nginx installed and configured
- [ ] SSL certificates obtained (Let's Encrypt or Azure)

### Odoo Setup
- [ ] Database initialized
- [ ] Kassa module installed
- [ ] Admin user created
- [ ] Accessible via `https://kassa.<domain>`

### Services
- [ ] RabbitMQ users configured
- [ ] Virtual host created (`/kassa`)
- [ ] POS Receiver connected to RabbitMQ
- [ ] Heartbeat service active

### Monitoring
- [ ] Logs collection configured
- [ ] Database backups scheduled
- [ ] RabbitMQ management accessible at port 15671
- [ ] Health checks passing

---

## 🔗 Related Documentation

These documents work together:

1. **[ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md)**
   - Read first to understand all available variables
   - Reference when adding new environment-specific configuration
   - Check "Troubleshooting" section for common issues

2. **[docker-compose.production.yml](./docker-compose.production.yml)**
   - Use as basis for production deployment
   - Read comments to understand each service's configuration
   - Compare with existing `docker-compose.yml` for differences

3. **[.env.example](./.env.example)**
   - Copy to `.env` to start configuration
   - Follow checklist for production deployment
   - Use different `.env` files for different environments

4. **[AZURE_DEPLOYMENT_GUIDE.md](./AZURE_DEPLOYMENT_GUIDE.md)**
   - Follow step-by-step for initial deployment
   - Reference nginx configuration section
   - Use troubleshooting guide when issues occur

5. **[CODE_EXAMPLES_ENV_VARIABLES.md](./CODE_EXAMPLES_ENV_VARIABLES.md)**
   - Use configuration module pattern in Python code
   - Copy RabbitMQ utilities for your services
   - Reference when implementing new integrations

---

## 📞 Common Questions

### Q: Should I keep internal service names (db, rabbitmq) or use Azure hostnames?
**A**: 
- **Development/Docker**: Use internal names (`db`, `rabbitmq`)
- **Production with Docker**: Use internal names for performance
- **External Services**: Use Azure managed service hostnames instead

### Q: Why is RabbitMQ Management on 15671 but AMQP on 5672?
**A**: 
- **5672**: AMQP protocol (message broker - for publishing/consuming)
- **15671**: HTTPS Management UI (admin interface - for monitoring)
- Services connect using AMQP (5672)
- Administrators access Management UI (15671) via Nginx

### Q: Can I commit the .env file to Git?
**A**: 
- **NO** - It contains passwords
- Add `.env` to `.gitignore`
- Use `.env.example` as template (no real values)
- Production: Use Azure Key Vault instead

### Q: How do services communicate internally?
**A**: 
- All services on same Docker network (`kassa-network`)
- Service names resolve automatically (e.g., `odoo:8069`, `rabbitmq:5672`)
- No need for IP addresses or hostnames

### Q: What if RabbitMQ or database is external (not Docker)?
**A**:
- Update `RABBIT_HOST` to external hostname
- Update `DB_HOST` to external hostname
- Keep ports the same (5672, 5432)
- Ensure Azure NSG allows outbound traffic

---

## 🛠️ Troubleshooting Matrix

| Issue | Check First | Reference |
|-------|------------|-----------|
| RabbitMQ connection refused | `RABBIT_HOST=rabbitmq`, `RABBIT_PORT=5672` | ENVIRONMENT_VARIABLES.md |
| PostgreSQL connection error | `DB_HOST=db`, database credentials | ENVIRONMENT_VARIABLES.md |
| Odoo not starting | Check logs: `docker compose -f docker-compose.production.yml logs odoo` | AZURE_DEPLOYMENT_GUIDE.md |
| 502 Bad Gateway from Nginx | Verify Odoo port mapping (8069 and 8072) | AZURE_DEPLOYMENT_GUIDE.md |
| RabbitMQ auth failed | Verify `RABBIT_USER` and `RABBIT_PASSWORD` | CODE_EXAMPLES_ENV_VARIABLES.md |
| Module not loading | Ensure `/mnt/extra-addons/kassa_pos` mounted | AZURE_DEPLOYMENT_GUIDE.md |

---

## 📊 Environment Variables Summary

### Total Variables: 19 Core + Additional Optional

**Core Variables** (required for production):
```
POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, DB_HOST, DB_PORT
RABBIT_HOST, RABBIT_PORT, RABBIT_USER, RABBIT_PASSWORD, RABBIT_VHOST
ODOO_PORT, ODOO_LONGPOLLING_PORT, ODOO_DOMAIN
```

**Service-Specific Variables**:
```
HEARTBEAT_INTERVAL_SECONDS, HEARTBEAT_EXCHANGE, HEARTBEAT_ROUTING_KEY, HEARTBEAT_QUEUE
POS_EXCHANGE, POS_ROUTING_KEY, POS_QUEUE
```

See **[ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md#environment-variables-table)** for complete table.

---

## 🎓 Learning Path

1. **Start**: Read this file (overview & context)
2. **Understand**: Review [ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md) (reference)
3. **Deploy**: Follow [AZURE_DEPLOYMENT_GUIDE.md](./AZURE_DEPLOYMENT_GUIDE.md) (step-by-step)
4. **Configure**: Use [docker-compose.production.yml](./docker-compose.production.yml) (implementation)
5. **Implement**: Reference [CODE_EXAMPLES_ENV_VARIABLES.md](./CODE_EXAMPLES_ENV_VARIABLES.md) (code patterns)

---

## 📝 Notes for Your Team

### For DevOps Engineers
- Use `.env.example` as baseline template
- Create `.env.production` with actual values (in Key Vault, not Git)
- Follow Azure_DEPLOYMENT_GUIDE.md for Nginx setup
- Monitor services via `docker compose -f docker-compose.production.yml logs`

### For Developers
- Reference CODE_EXAMPLES_ENV_VARIABLES.md for reading env vars
- Use Config class pattern for consistency
- Test with validation scripts before deployment
- See ENVIRONMENT_VARIABLES.md for complete list

### For Infrastructure Teams
- RabbitMQ Management UI requires HTTPS/15671
- Nginx must proxy Odoo main traffic (443 -> 8069), Odoo websocket (443 /websocket -> 8072), and RabbitMQ (15671 -> 15672)
- All internal services use Docker bridge network
- Implement backups for PostgreSQL data volume

---

## ✨ What's Next

1. **Edit `.env`** with your Azure infrastructure details
2. **Review docker-compose files** to understand the setup
3. **Configure Nginx** using the provided template
4. **Deploy** following the step-by-step guide
5. **Test** all services and connections
6. **Monitor** logs and health checks
7. **Backup** regularly

---

**Documentation Created**: April 4, 2026  
**Version**: 1.0  
**Status**: Production Ready ✅

For questions or clarifications, reference the specific documentation mentioned above.
