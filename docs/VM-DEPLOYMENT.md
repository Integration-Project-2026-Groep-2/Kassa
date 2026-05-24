# VM Deployment Guide - Kassa POS

This VM setup uses the custom Odoo image `ghcr.io/teamkassa/odoo-kassa:latest` with a baked-in entrypoint and Odoo config. The realtime port is handled automatically by the entrypoint, so the same deployment works for both older and newer Odoo images.

## Scenario 1: All on VM (Odoo + RabbitMQ + Python Services)

### Setup steps:

```bash
# 1. Clone project and install dependencies
cd /path/to/Kassa
python3 -m venv venv
source venv/bin/activate  # Or: venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt

# 2. Start Docker services
docker compose up -d --build

# 3. Deploy custom Odoo image from GHCR
export ODOO_IMAGE=ghcr.io/<org-of-user>/odoo-kassa:latest
docker compose -f docker-compose.production.yml pull odoo
docker compose -f docker-compose.production.yml up -d

# 3a. If this VM already has an older database: run a one-time module upgrade
docker compose -f docker-compose.production.yml exec odoo odoo -c /etc/odoo/odoo.conf -d "$POSTGRES_DB" -u kassa_pos --stop-after-init

# 3b. Important for VM deployments
# - Odoo runs from the GHCR image, not from a bind-mounted copy with shell scripts
# - Odoo data lives in a bind-mount or project volume; Odoo sessions go to a writable tmp location
# - The entrypoint automatically selects the correct realtime flag for the Odoo version in the image
# - Module upgrades are opt-in; set `ODOO_SYNC_MODULES=kassa_pos` only if you intentionally want to force a reinstall

# 4. Initialize database (one-time)
docker compose run --rm odoo odoo --db_host=db --db_user=odoo --db_password=odoo -d odoo -i base --without-demo=all --stop-after-init

# 5. Start Python services
cd src

# Terminal 1: POS Receiver
RABBIT_HOST=localhost python main_pos_receiver.py
```

### Access services:
- **Odoo**: `http://<VM-IP>:8069`
- **RabbitMQ Management**: `http://<VM-IP>:15672` (guest/guest)

### Realtime port
- The container also exposes internal port `8072` for websocket/gevent/longpolling traffic
- This port usually does not need to be open externally if Nginx handles the reverse proxy
- The entrypoint automatically selects the correct Odoo flag for the realtime port

---

## Scenario 2: Docker op VM, Python services op extern machine

### On the VM:
```bash
# Ensure ports are exposed
docker compose up -d

# Check Docker IP
docker inspect -f '{{.Name}} {{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $(docker ps -q)
```

### On the external machine (Windows/Linux):
```bash
# Set RabbitMQ host to VM IP
export RABBIT_HOST=<VM-IP>  # or 10.0.0.X etc.

# Start services
cd src
python main_pos_receiver.py
```

---

## Environment variables

```bash
# RabbitMQ host (production)
RABBIT_HOST=<VM-IP of hostname>

# For local Docker network (alt)
RABBIT_HOST=rabbitmq
```

---

## Port bindings (docker-compose.yml)

```yaml
odoo:
  ports:
    - "0.0.0.0:8069:8069"  # ALL interfaces
    - "0.0.0.0:8072:8072"  # Realtime verkeer (websocket/gevent/longpolling)

rabbitmq:
  ports:
    - "0.0.0.0:5672:5672"   # ALL interfaces
    - "0.0.0.0:15672:15672" # Management UI
```

---

## Troubleshooting

**Odoo server: error: no such option: --longpolling-port**:
- The VM uses an Odoo image where the realtime port is handled via `--gevent-port`
- Ensure you use the latest `docker/odoo-entrypoint.sh` from this repo
- Rebuild the image: `docker compose -f docker-compose.production.yml build odoo`

**/var/lib/odoo/sessions not writable**:
- The production config now uses a separate writable `session_dir` under `/tmp`
- If your config differs, ensure `session_dir` is not on a non-writable volume

**Connection refused from remote machine**:
- Verify ports open: `netstat -an | grep 5672` (Linux) of `netstat -ano | findstr 5672` (Windows)
- Check firewall rules

**RabbitMQ not found from Python**:
- Ensure the `RABBIT_HOST` environment variable is set
- Test connectivity: `ping <RABBIT_HOST>`

**IPv6 vs IPv4 issues (Windows)**:
- Use `127.0.0.1` instead of `localhost` in connection strings
- `Connection.py` automatically resolves this

**Module skips / filestore warnings in the Odoo log**:
- These messages are expected with the current image/database combination and do not stop the VM
- They usually point to optional modules or older database attachments, not a startup failure
- Focus on real blockers such as `bash\r`, invalid Odoo flags or write-permission errors
