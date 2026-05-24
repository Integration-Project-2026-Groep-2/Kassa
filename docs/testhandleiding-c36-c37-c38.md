# Test Guide — C36, C37, C38: Forward CRUD XML to CRM

**Branch:** `crud-xml-to-crm`  
**Team:** Team Kassa  
**What is tested:** Automatic forwarding of user create / update / deactivate events to CRM via RabbitMQ

---

## Requirements

-- Docker Desktop installed and running
-- Git installed
-- Ports 8069, 15672 and 5672 open on your machine

---

## Step 1 — Clone project and start

```bash
git clone <repo-url>
cd Kassa
git checkout crud-xml-to-crm
```

Create an `odoo.conf` based on the example:

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

Je moet `[INFO] Heartbeat verzonden` zien also Odoo klaar is.

---

## Step 2 — Create RabbitMQ test queue

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

## Step 3 — Test C36 (create user)

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

**Expected result in terminal:**
```
C36 resultaat: True
```

**Check in RabbitMQ:**
1. Ga naar `test.crm.kassa` queue
2. Scroll naar **Get messages** → Ack Mode: `Nack message requeue true` → klik **Get Message(s)**
3. Je ziet:

| Field | Expected value |
|------|-----------------|
| Exchange | `user.topic` |
| Routing Key | `kassa.user.created` |
| content_type | `application/xml` |
| Payload | `<KassaUserCreated><userId>test-crm-uuid-001</userId>...` |

---

## Step 4 — Test C37 (update user)

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

**Controleer in RabbitMQ** (zelfde stappen also stap 3):

| Veld | Verwachte waarde |
|------|-----------------|
| Routing Key | `kassa.user.updated` |
| Payload | `<KassaUserUpdated><userId>test-crm-uuid-001</userId>...` |

---

## Step 5 — Test C38 (deactivate user)

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

**Controleer in RabbitMQ** (zelfde stappen also stap 3):

| Veld | Verwachte waarde |
|------|-----------------|
| Routing Key | `kassa.user.deactivated` |
| Payload | `<UserDeactivated><id>test-crm-uuid-001</id>...` |

> Note: C38 uses `<id>` (not `<userId>`), per the contract with CRM.

---

## Step 6 — Test automatic trigger via Odoo

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

Then check in RabbitMQ whether a `<KassaUserCreated>` message appears.

---


## Overview of expected messages

After all tests you should see 4 messages in the queue:

| # | Routing Key | XML Element |
|---|-------------|-------------|
| 1 | `kassa.user.created` | `<KassaUserCreated>` |
| 2 | `kassa.user.updated` | `<KassaUserUpdated>` |
| 3 | `kassa.user.deactivated` | `<UserDeactivated>` |
| 4 | `kassa.user.created` | `<KassaUserCreated>` (automatic trigger) |

---

## Problems?

| Problem | Solution |
|----------|-----------|
| `C36 result: False` | Check RabbitMQ is running: `docker compose ps` |
| `user.topic` exchange not visible | Run `docker compose restart odoo` and try again |
| Odoo not reachable on port 8069 | Wait 2 more minutes and refresh — fresh install can take 3-5 min |
| Queue empty after test | Check binding is correct: `user.topic` → `kassa.user.*` |
