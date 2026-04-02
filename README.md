# Team Kassa Docker Deliverables

Dit project levert een custom Odoo image (gebaseerd op de officiele `odoo:17` image) met Team Kassa code ingebakken.

## 1) Docker images

- App image: bouw met `docker build -t teamkassa/odoo-kassa:17 .`
	Deze image bevat:
	- Odoo 17 (officiele base image)
	- `kassa_pos` addon
	- RabbitMQ messaging scripts (`src/` + `templates/`)
	- Python package `pika`
- DB image: `postgres:15`
- RabbitMQ image: `rabbitmq:3-management`

## 2) Vereiste environment variables

Gebruik `.env.example` als basis.

| Variabele | Beschrijving | Voorbeeld |
|---|---|---|
| `POSTGRES_DB` | Odoo database naam | `kassa_db` |
| `POSTGRES_USER` | PostgreSQL user | `kassa` |
| `POSTGRES_PASSWORD` | PostgreSQL wachtwoord | `change_me_db_password` |
| `DB_HOST` | PostgreSQL host voor Odoo | `db` |
| `DB_PORT` | PostgreSQL poort | `5432` |
| `ODOO_PORT` | Exposed Odoo HTTP poort | `8069` |
| `RABBIT_HOST` | RabbitMQ host | `rabbitmq` |
| `RABBIT_PORT` | RabbitMQ AMQP poort | `5672` |
| `RABBIT_MANAGEMENT_PORT` | RabbitMQ management UI poort | `15672` |
| `RABBIT_USER` | RabbitMQ user | `team_kassa` |
| `RABBIT_PASSWORD` | RabbitMQ wachtwoord | `change_me_secure` |
| `RABBIT_VHOST` | RabbitMQ vhost | `/` |
| `HEARTBEAT_INTERVAL_SECONDS` | Heartbeat interval in seconden | `1` |
| `HEARTBEAT_EXCHANGE` | Exchange voor heartbeat | `heartbeat.direct` |
| `HEARTBEAT_ROUTING_KEY` | Routing key voor heartbeat | `routing.heartbeat` |
| `HEARTBEAT_QUEUE` | Queue voor heartbeat | `heartbeat_queue` |

## 3) Eerste opstart (manuele stap)

Na de eerste `docker compose up -d --build` moet de Odoo database geinitialiseerd worden.

Gebruik:

```bash
docker compose exec odoo odoo \
	-d ${POSTGRES_DB} \
	-i base \
	--without-demo=all \
	--stop-after-init \
	--db_host=${DB_HOST} \
	--db_port=${DB_PORT} \
	--db_user=${POSTGRES_USER} \
	--db_password=${POSTGRES_PASSWORD}
```

Daarna Odoo herstarten:

```bash
docker compose restart odoo
```

## 4) Minimale compose setup

Een werkende referentie staat in `docker-compose.yml` in deze repository.

Starten:

```bash
cp .env.example .env
docker compose up -d --build
```

Controle:

```bash
docker compose ps
docker compose logs --tail=100 odoo rabbitmq heartbeat pos_receiver
```
