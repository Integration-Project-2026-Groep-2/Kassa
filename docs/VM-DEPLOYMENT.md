# VM Deployment Guide - Kassa POS

Deze VM-setup gebruikt de custom Odoo image `ghcr.io/teamkassa/odoo-kassa:latest` met een ingebakken entrypoint en Odoo-config. De realtime poort wordt automatisch afgehandeld door de entrypoint, zodat dezelfde deployment werkt voor zowel oudere als nieuwere Odoo-images.

## Scenario 1: Alles op VM (Odoo + RabbitMQ + Python Services)

### Setup stappen:

```bash
# 1. Clone project en instál dependencies
cd /path/to/Kassa
python3 -m venv venv
source venv/bin/activate  # Atau: venv\Scripts\Activate.ps1 op Windows
pip install -r requirements.txt

# 2. Start Docker services
docker compose up -d --build

# 3. Deploy custom Odoo image from GHCR
export ODOO_IMAGE=ghcr.io/<org-of-user>/odoo-kassa:latest
docker compose -f docker-compose.production.yml pull odoo
docker compose -f docker-compose.production.yml up -d

# 3b. Belangrijk voor VM-deployments
# - Odoo draait uit de GHCR image, niet uit een losse bind mount met shell scripts
# - De data van Odoo staat in een managed Docker volume, zodat /var/lib/odoo/sessions schrijfbaar blijft
# - De entrypoint kiest automatisch de juiste realtime flag voor de Odoo-versie in de image

# 4. Initialize database (eenmalig)
docker compose run --rm odoo odoo --db_host=db --db_user=odoo --db_password=odoo -d odoo -i base --without-demo=all --stop-after-init

# 5. Start Python services
cd src

# Terminal 1: POS Receiver
RABBIT_HOST=localhost python main_pos_receiver.py
```

### Access services:
- **Odoo**: `http://<VM-IP>:8069`
- **RabbitMQ Management**: `http://<VM-IP>:15672` (guest/guest)

### Realtime poort
- De container exposeert intern ook `8072` voor websocket/gevent/longpolling-verkeer
- Deze poort hoeft meestal niet extern open als Nginx de reverse proxy afhandelt
- De entrypoint kiest automatisch de juiste Odoo-flag voor die realtime poort

---

## Scenario 2: Docker op VM, Python services op extern machine

### Op VM:
```bash
# Zorg dat ports exposed zijn
docker compose up -d

# Check Docker IP
docker inspect -f '{{.Name}} {{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $(docker ps -q)
```

### Op extern machine (Windows/Linux):
```bash
# Set RabbitMQ host naar VM-IP
export RABBIT_HOST=<VM-IP>  # of 10.0.0.X etc.

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
- De VM gebruikt een Odoo image waarbij de realtime poort via `--gevent-port` wordt afgehandeld
- Controleer dat je de nieuwste `docker/odoo-entrypoint.sh` uit deze repo gebruikt
- Rebuild de image: `docker compose -f docker-compose.production.yml build odoo`

**/var/lib/odoo/sessions not writable**:
- Gebruik de production compose zoals aangeleverd; daar draait Odoo met een managed volume
- Als je zelf volumes aanpast, vermijd een root-owned bind mount voor `/var/lib/odoo`

**Connection refused from remote machine**:
- Verifiy ports open: `netstat -an | grep 5672` (Linux) of `netstat -ano | findstr 5672` (Windows)
- Check firewall rules

**RabbitMQ not found from Python**:
- Zorg RABBIT_HOST omgevingsvariabele is ingesteld
- Test connectivity: `ping <RABBIT_HOST>`

**IPv6 vs IPv4 issues (Windows)**:
- Use `127.0.0.1` instead of `localhost` in connection strings
- Connection.py automatisch resolveert dit

**Module skips / filestore warnings in the Odoo log**:
- Deze meldingen zijn expected met de huidige image/database combinatie en stoppen de VM niet
- Ze wijzen meestal op optionele modules of oudere database-attachments, niet op een startup failure
- Focus op echte blockers zoals `bash\r`, ongeldige Odoo flags of write-permission errors
