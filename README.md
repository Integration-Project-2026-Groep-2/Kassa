# Team Kassa

Starter project voor Team Kassa van het Integration Project.

## Wat dit project bevat
- RabbitMQ sender
- RabbitMQ receiver
- heartbeat
- statuscheck
- XML-validatie via XSD
- Odoo client starter code

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python src/main.py
```

## Belangrijk
- Gebruik XML voor alle berichten
- Valideer inkomende en uitgaande berichten tegen het XSD-schema
- Commit nooit credentials of .env

## Belangrijkste files
- src/main.py - start de app
- src/messaging/connection.py - RabbitMQ connectie
- src/messaging/sender.py - publiceert berichten
- src/messaging/receiver.py - ontvangt berichten
- src/odoo/client.py - Odoo integratie
- src/schema/kassa-schema-v1.xsd - XSD validatie