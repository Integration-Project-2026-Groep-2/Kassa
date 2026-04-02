# Kassa

## RabbitMQ credentials via .env

Gebruik geen hardcoded `guest/guest` in code. Dit project leest RabbitMQ-instellingen via environment variables.

1. Maak een lokale env file:
- Kopieer `.env.example` naar `.env`
2. Pas credentials aan in `.env`:
- `RABBIT_USER`
- `RABBIT_PASSWORD`
- `RABBIT_VHOST`
3. Start de stack opnieuw:
- `docker compose down`
- `docker compose up -d --build`

## Welke credentials gebruiken andere teams?

Dat bepaalt elk team zelf in hun eigen `.env` file.

Voorbeeld:
- Team A gebruikt `RABBIT_USER=team_a`
- Team B gebruikt `RABBIT_USER=team_b`

Zolang de waarden in `.env` kloppen, gebruiken `odoo`, `pos_receiver` en `heartbeat` automatisch diezelfde credentials.

## Belangrijkste env variabelen

- `RABBIT_HOST` (in Docker meestal `rabbitmq`)
- `RABBIT_PORT` (standaard `5672`)
- `RABBIT_USER`
- `RABBIT_PASSWORD`
- `RABBIT_VHOST`
- `HEARTBEAT_INTERVAL_SECONDS`
