# Testhandleiding — C36, C37, C38: CRUD XML Doorsturen naar CRM

**Branch:** `crud-xml-to-crm`  
**Team:** Team Kassa  
**Wat wordt getest:** Automatisch doorsturen van user aanmaken / bijwerken / deactiveren naar CRM via RabbitMQ

---

## Vereisten

- Docker Desktop geïnstalleerd en draaiend
- Git geïnstalleerd
- Poorten 8069, 15672 en 5672 vrij op je machine

---

## Stap 1 — Project ophalen en starten

```bash
git clone <repo-url>
cd Kassa
git checkout crud-xml-to-crm
```

Maak een `odoo.conf` aan op basis van het voorbeeld:

```bash
cp odoo.conf.example odoo.conf
```

Start de containers:

```bash
docker compose up -d --build
```

Wacht 3-5 minuten totdat Odoo volledig opgestart is. Controleer met:

```bash
docker compose logs odoo --tail=10
```

Je moet `[INFO] Heartbeat verzonden` zien als Odoo klaar is.

---

## Stap 2 — RabbitMQ testqueue aanmaken

1. Ga naar [http://localhost:15672](http://localhost:15672)
2. Login:
   - Username: `team_kassa`
   - Password: `kassa_local_dev`
3. Klik bovenaan op **Queues and Streams**
4. Scroll naar beneden → **Add a new queue**
   - Type: `Classic`
   - Virtual host: `/`
   - Name: `test.crm.kassa`
   - Durability: `Durable`
5. Klik op **Add queue**
6. Klik op de nieuwe queue `test.crm.kassa`
7. Scroll naar **Bindings** → **Add binding from exchange**
   - From exchange: `user.topic`
   - Routing key: `kassa.user.*`
8. Klik op **Bind**

---

## Stap 3 — C36 testen (gebruiker aanmaken)

Voer dit commando uit in de terminal:

```bash
docker compose exec odoo python3 -c "
import sys, os, importlib.util
os.environ['RABBIT_HOST'] = 'rabbitmq'
os.environ['RABBIT_USER'] = 'team_kassa'
os.environ['RABBIT_PASSWORD'] = 'kassa_local_dev'
os.environ['RABBIT_VHOST'] = '/'
spec = importlib.util.spec_from_file_location('rabbitmq_sender', '/mnt/extra-addons/kassa_pos/utils/rabbitmq_sender.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
result = mod.send_kassa_user_created({
    'userId': 'test-crm-uuid-001',
    'firstName': 'Test',
    'lastName': 'Gebruiker',
    'email': 'test@test.com',
    'badgeCode': 'CRM001',
    'role': 'CASHIER',
    'createdAt': '2026-04-29T10:00:00Z',
})
print('C36 resultaat:', result)
"
```

**Verwacht resultaat in terminal:**
```
C36 resultaat: True
```

**Controleer in RabbitMQ:**
1. Ga naar `test.crm.kassa` queue
2. Scroll naar **Get messages** → Ack Mode: `Nack message requeue true` → klik **Get Message(s)**
3. Je ziet:

| Veld | Verwachte waarde |
|------|-----------------|
| Exchange | `user.topic` |
| Routing Key | `kassa.user.created` |
| content_type | `application/xml` |
| Payload | `<KassaUserCreated><userId>test-crm-uuid-001</userId>...` |

---

## Stap 4 — C37 testen (gebruiker bijwerken)

```bash
docker compose exec odoo python3 -c "
import sys, os, importlib.util
os.environ['RABBIT_HOST'] = 'rabbitmq'
os.environ['RABBIT_USER'] = 'team_kassa'
os.environ['RABBIT_PASSWORD'] = 'kassa_local_dev'
os.environ['RABBIT_VHOST'] = '/'
spec = importlib.util.spec_from_file_location('rabbitmq_sender', '/mnt/extra-addons/kassa_pos/utils/rabbitmq_sender.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
result = mod.send_kassa_user_updated({
    'userId': 'test-crm-uuid-001',
    'firstName': 'Test',
    'lastName': 'Gebruiker',
    'email': 'test@test.com',
    'badgeCode': 'CRM001',
    'role': 'CASHIER',
    'updatedAt': '2026-04-29T11:00:00Z',
})
print('C37 resultaat:', result)
"
```

**Verwacht resultaat in terminal:**
```
C37 resultaat: True
```

**Controleer in RabbitMQ** (zelfde stappen als stap 3):

| Veld | Verwachte waarde |
|------|-----------------|
| Routing Key | `kassa.user.updated` |
| Payload | `<KassaUserUpdated><userId>test-crm-uuid-001</userId>...` |

---

## Stap 5 — C38 testen (gebruiker deactiveren)

```bash
docker compose exec odoo python3 -c "
import sys, os, importlib.util
os.environ['RABBIT_HOST'] = 'rabbitmq'
os.environ['RABBIT_USER'] = 'team_kassa'
os.environ['RABBIT_PASSWORD'] = 'kassa_local_dev'
os.environ['RABBIT_VHOST'] = '/'
spec = importlib.util.spec_from_file_location('rabbitmq_sender', '/mnt/extra-addons/kassa_pos/utils/rabbitmq_sender.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
result = mod.send_kassa_user_deactivated('test-crm-uuid-001', 'test@test.com')
print('C38 resultaat:', result)
"
```

**Verwacht resultaat in terminal:**
```
C38 resultaat: True
```

**Controleer in RabbitMQ** (zelfde stappen als stap 3):

| Veld | Verwachte waarde |
|------|-----------------|
| Routing Key | `kassa.user.deactivated` |
| Payload | `<UserDeactivated><id>test-crm-uuid-001</id>...` |

> Let op: C38 gebruikt `<id>` (niet `<userId>`), conform het contract met CRM.

---

## Stap 6 — Automatische trigger via Odoo testen

Dit test of de berichten ook automatisch verstuurd worden wanneer een contact aangemaakt wordt in Odoo (zonder handmatig commando).

```bash
docker compose exec odoo python3 -c "
import odoo
odoo.tools.config.parse_config(['-d', 'kassa_db'])
from odoo import api, SUPERUSER_ID
from odoo.modules.registry import Registry
registry = Registry('kassa_db')
with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    partner = env['res.partner'].create({
        'name': 'Automatische Test',
        'email': 'auto@test.com',
        'user_id_custom': 'auto-uuid-001',
        'badge_code': 'AUTO001',
        'role': 'Cashier',
    })
    cr.commit()
    print('Contact aangemaakt:', partner.id, partner.name)
"
```

Controleer daarna in RabbitMQ of er een `<KassaUserCreated>` bericht verschijnt.

---

## Overzicht verwachte berichten

Na alle tests zie je 4 berichten in de queue:

| # | Routing Key | XML Element |
|---|-------------|-------------|
| 1 | `kassa.user.created` | `<KassaUserCreated>` |
| 2 | `kassa.user.updated` | `<KassaUserUpdated>` |
| 3 | `kassa.user.deactivated` | `<UserDeactivated>` |
| 4 | `kassa.user.created` | `<KassaUserCreated>` (automatische trigger) |

---

## Problemen?

| Probleem | Oplossing |
|----------|-----------|
| `C36 resultaat: False` | Controleer of RabbitMQ draait: `docker compose ps` |
| `user.topic` exchange niet zichtbaar | Voer `docker compose restart odoo` uit en probeer opnieuw |
| Odoo niet bereikbaar op poort 8069 | Wacht nog 2 minuten en refresh — fresh install duurt 3-5 min |
| Queue leeg na test | Controleer of de binding correct is: `user.topic` → `kassa.user.*` |
