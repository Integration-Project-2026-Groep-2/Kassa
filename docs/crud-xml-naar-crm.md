# Forward CRUD XML to CRM — Technical Documentation

**Project:** Integration Project 2025/2026 — Group 2  
**Team:** Team Kassa  
**Purpose:** Contracts C36, C37, C38 — Kassa → CRM user lifecycle  
**Date:** April 2026

---

# Forward CRUD XML to CRM — Technical Documentation

**Project:** Integration Project 2025/2026 — Group 2  
**Team:** Team Kassa  
**Purpose:** Contracts C36, C37, C38 — Kassa → CRM user lifecycle  
**Date:** April 2026

## Contents

1. [Overview](#1-overview)
2. [Contracts](#2-contracts)
3. [Architecture](#3-architecture)
4. [Changed and new files](#4-changed-and-new-files)
5. [XML Messages](#5-xml-messages)
6. [RabbitMQ configuration](#6-rabbitmq-configuration)
7. [How it works](#7-how-it-works)
8. [Testing](#8-testing)
9. [Resolved bugs](#9-resolved-bugs)

## 1. Overview

When a user is created, updated or deleted in Odoo (Kassa), the system automatically sends an XML message to CRM via RabbitMQ. CRM uses these messages to keep its user store synchronized with Kassa.

**Flow:**

```
Odoo (res.partner) → rabbitmq_sender.py → RabbitMQ user.topic exchange → CRM
```

--- 

## 2. Contracts

| Contract | Actie        | Routing Key            | XML Element         | CRM Queue                   |
|----------|--------------|------------------------|---------------------|-----------------------------|
| C36      | Create       | `kassa.user.created`   | `<KassaUserCreated>` | `crm.kassa.user.created`   |
| C37      | Update       | `kassa.user.updated`   | `<KassaUserUpdated>` | `crm.kassa.user.updated`   |
| C38      | Deactivate   | `kassa.user.deactivated` | `<UserDeactivated>` | `crm.kassa.user.deactivated` |

**Important for C38:** the key field is `<id>` (not `<userId>`), per the CRM XSD spec.

---

## 3. Architecture

### RabbitMQ Exchange

| Exchange    | Type  | Durable | Purpose                            |
|-------------|-------|---------|-----------------------------------|
| `user.topic` | topic | yes     | Shared with CRM, Invoicing, Mailing, Scheduling |

Kassa **only publishes** to the exchange using a routing key.  
CRM **declares its own** consumer queues and binds them to the exchange.

### Why topic exchange?

A `topic` exchange allows multiple teams to listen to the same messages using wildcards. CRM binds their queue with `kassa.user.*` so they receive all three routing keys.

### Automatic trigger

Messages are sent via Odoo ORM hooks in [kassa_pos/models/res_partner.py](../kassa_pos/models/res_partner.py):

- `create()` → calls `_publish_user_change('created')` → C36
- `write()` → calls `_publish_user_change('updated')` → C37 (only when one of the relevant fields changed)
- `unlink()` → calls `_publish_user_deleted()` → C38

**Prerequisite:** the contact must have a `user_id_custom` (User ID) set. Contacts without a User ID are not forwarded.

### Watched fields for C37

An update message is only sent when one of these fields is changed:
- `name`, `email`, `phone`, `badge_code`, `role`, `company_id_custom`, `user_id_custom`

---

## 4. Changed and new files

### New file

#### `src/schema/contracts/kassa-user.xsd`
Standalone XSD schema version 1.10.1 for C36/C37/C38.

This schema is separate from the master schema (`kassa-schema-v1.xsd`) because `<UserDeactivated>` conflicts with Contract 22 in the master schema.

Defines:
- `KassaUserCreated` (C36)
- `KassaUserUpdated` (C37)
- `UserDeactivated` (C38)
- `NonEmptyStringType` — prevents empty `<badgeCode>` (minLength=1)

### Changed files

#### `kassa_pos/utils/rabbitmq_sender.py`

Added:
- `USER_TOPIC_EXCHANGE = 'user.topic'`
- Routing key constants: `ROUTING_KEY_KASSA_USER_CREATED`, `ROUTING_KEY_KASSA_USER_UPDATED`, `ROUTING_KEY_KASSA_USER_DEACTIVATED`
- `_build_kassa_user_created_xml()` — builds `<KassaUserCreated>` XML
- `_build_kassa_user_updated_xml()` — builds `<KassaUserUpdated>` XML
- `_build_kassa_user_deactivated_xml()` — builds `<UserDeactivated>` XML with `<id>` field
- `_publish_to_topic_exchange()` — publishes to `user.topic` without declaring consumer queues
- `send_kassa_user_created()` — public function for C36
- `send_kassa_user_updated()` — public function for C37
- `send_kassa_user_deactivated()` — public function for C38

#### `kassa_pos/models/res_partner.py`

Added:
- `_publish_to_crm()` — calls the CRM sender functions
- `unlink()` — captures email before deletion (needed for C38)
- `_publish_user_deleted()` — accepts email parameter and sends C38

Changed:
- `_publish_user_change()` — now calls `_publish_to_crm()` in addition to the internal queue
- `_build_user_created_payload_xml()` — produces `<UserCreated>` (was `<User>`)
- `_build_user_updated_payload_xml()` — produces `<UserUpdatedIntegration>` (was `<User>`)

#### `src/xml_validator.py`

Added:
- `KASSA_USER_SCHEMA_PATH` — path to `kassa-user.xsd`
- `_kassa_schema` — loaded standalone schema
- `validate_kassa(xml_string)` — validates C36/C37/C38 messages, returns `(bool, str|None)`

#### `setup_rabbitmq.py`

Added:
- `user.topic` exchange in the list of exchanges to declare
- Use of environment variables for connection settings (was hardcoded)

---

## 5. XML Messages

### C36 — KassaUserCreated

```xml
<KassaUserCreated>
  <userId>550e8400-e29b-41d4-a716-446655440000</userId>
  <firstName>Jan</firstName>
  <lastName>Janssen</lastName>
  <email>jan@example.com</email>
  <companyId>9c21f4e1-8b2e-4d71-a7a2-6f8cbbf81c10</companyId>  <!-- optional -->
  <badgeCode>BADGE001</badgeCode>
  <role>CASHIER</role>
  <createdAt>2026-04-29T12:00:00Z</createdAt>
</KassaUserCreated>
```

### C37 — KassaUserUpdated

```xml
<KassaUserUpdated>
  <userId>550e8400-e29b-41d4-a716-446655440000</userId>
  <firstName>Jan</firstName>
  <lastName>Janssen</lastName>
  <email>jan@example.com</email>
  <badgeCode>BADGE001</badgeCode>
  <role>CASHIER</role>
  <updatedAt>2026-04-29T13:00:00Z</updatedAt>
</KassaUserUpdated>
```

### C38 — UserDeactivated

```xml
<UserDeactivated>
  <id>550e8400-e29b-41d4-a716-446655440000</id>
  <email>jan@example.com</email>
  <deactivatedAt>2026-04-29T14:00:00Z</deactivatedAt>
</UserDeactivated>
```

**Note:** C38 uses `<id>` (not `<userId>`), according to the agreement with CRM.

### Allowed roles

| Odoo value | XML value        |
|-------------|-------------------|
| Customer    | VISITOR           |
| Cashier     | CASHIER           |
| Admin       | ADMIN             |

---

## 6. RabbitMQ configuration

### Declare exchange

The `user.topic` exchange is declared by `setup_rabbitmq.py`. This script can be run manually:

```bash
docker compose exec odoo python3 /app/setup_rabbitmq.py
```

Or add it manually via the RabbitMQ Management UI:
1. Go to [http://localhost:15672](http://localhost:15672)
2. Login: `team_kassa` / `kassa_local_dev`
3. Exchanges → Add a new exchange
   - Name: `user.topic`
   - Type: `topic`
   - Durability: Durable

### Connection settings (from .env)

| Variable         | Value       |
|-------------------|--------------|
| `RABBIT_HOST`     | `rabbitmq`   |
| `RABBIT_PORT`     | `5672`       |
| `RABBIT_USER`     | `team_kassa` |
| `RABBIT_PASSWORD` | `kassa_local_dev` |
| `RABBIT_VHOST`    | `/`          |

---

## 7. How it works

1. The administrator creates a new contact in Odoo with a **User ID** filled in
2. Odoo calls `res_partner.create()`
3. `_publish_user_change('created')` is triggered
4. `_publish_to_crm('created', user_data)` calls `send_kassa_user_created()`
5. `_publish_to_topic_exchange()` connects to RabbitMQ and publishes the XML message
6. The message is on the `user.topic` exchange with routing key `kassa.user.created`
7. CRM receives the message via their own queue bound to `user.topic`

The same applies for C37 (on `write()`) and C38 (on `unlink()`).

---

## 8. Testing

### Manual test via terminal

**C36 — Create:**
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
    'lastName': 'User',
    'email': 'test@test.com',
    'badgeCode': 'CRM001',
    'role': 'CASHIER',
    'createdAt': '2026-04-29T10:00:00Z',
})
print('C36 result:', result)
"
```

**C37 — Update:** replace `send_kassa_user_created` with `send_kassa_user_updated` and `createdAt` with `updatedAt`.

**C38 — Deactivate:**
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
print('C38 result:', result)
"
```

### Check messages in RabbitMQ

1. Go to [http://localhost:15672](http://localhost:15672) → login `team_kassa`
2. Create a test queue: **Queues → Add a new queue** → name `test.crm.kassa`
3. Bind the queue: click on the queue → **Bindings → Add binding from exchange**
   - From exchange: `user.topic`
   - Routing key: `kassa.user.*`
4. Send a test message using the command above
5. Click on **Get Message(s)** to see the message

### Expected outcome on successful test

```
Exchange:     user.topic
Routing Key:  kassa.user.created  (or .updated / .deactivated)
Properties:   delivery_mode: 2, content_type: application/xml
Payload:      <KassaUserCreated>...</KassaUserCreated>
```

### Automatic test via contact creation in Odoo

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
        'name': 'Test CRM User',
        'email': 'testcrm@test.com',
        'user_id_custom': 'test-crm-uuid-001',
        'badge_code': 'CRM001',
        'role': 'Cashier',
    })
    cr.commit()
    print('Created:', partner.id, partner.name)
"
```

### Unit tests (XSD validation)

```bash
docker compose exec odoo python3 -m pytest src/tests/test_xml_validator.py -v
```

All 48 tests must pass, including 12 new tests for C36/C37/C38.

---

## 9. Resolved bugs

During the implementation, the following existing bugs were also resolved:

| Bug | Problem | Solution |
|-----|----------|-----------|
| Incorrect XML elements | `<User>` was used for both create and update | Split into `<UserCreated>` and `<UserUpdatedIntegration>` |
| Duplicate queue handler | `crm.user.confirmed` was listed twice in `QUEUE_HANDLERS`, causing ~50% of messages to be lost | Removed duplicate and merged handlers |
| Update/delete events not processed | `on_user_updated` and `on_user_deactivated` only logged, but did not update UserStore | Added `_user_consumer.process_user_message()` |
| `setup_rabbitmq.py` hardcoded credentials | Connection settings were hardcoded in the script | Used environment variables |
| `user.topic` exchange missing | Exchange was not automatically created on startup | Added to `setup_rabbitmq.py` |

---

## 1. Overview

When a user is created, updated or deleted in Odoo (Kassa), the system automatically sends an XML message to CRM via RabbitMQ. CRM uses these messages to keep its user store synchronized with Kassa.

**Flow:**
```
Odoo (res.partner) → rabbitmq_sender.py → RabbitMQ user.topic exchange → CRM
```

---

## 2. Contracts

| Contract | Actie        | Routing Key            | XML Element         | CRM Queue                   |
|----------|--------------|------------------------|---------------------|-----------------------------|
| C36      | Create       | `kassa.user.created`   | `<KassaUserCreated>` | `crm.kassa.user.created`   |
| C37      | Update       | `kassa.user.updated`   | `<KassaUserUpdated>` | `crm.kassa.user.updated`   |
| C38      | Deactivate   | `kassa.user.deactivated` | `<UserDeactivated>` | `crm.kassa.user.deactivated` |

**Important for C38:** the key field is `<id>` (not `<userId>`), per the CRM XSD spec.

---

## 3. Architecture

### RabbitMQ Exchange

| Exchange    | Type  | Durable | Purpose                            |
|-------------|-------|---------|-----------------------------------|
| `user.topic` | topic | yes     | Shared with CRM, Invoicing, Mailing, Scheduling |

Kassa **publiceert alleen** naar de exchange met een routing key.  
CRM **declareert zelf** hun consumer-queues en bindt die aan de exchange.

### Why topic exchange?

A `topic` exchange allows multiple teams to listen to the same messages using wildcards. CRM binds their queue with `kassa.user.*` so they receive all three routing keys.

### Automatic trigger

Messages are sent via Odoo ORM hooks in [kassa_pos/models/res_partner.py](../kassa_pos/models/res_partner.py):

- `create()` → roept `_publish_user_change('created')` aan → C36
- `write()` → roept `_publish_user_change('updated')` aan → C37 (alleen also relevant velden gewijzigd zijn)
- `unlink()` → roept `_publish_user_deleted()` aan → C38

**Prerequisite:** the contact must have a `user_id_custom` (User ID) set. Contacts without a User ID are not forwarded.

### Watched fields for C37

Een update-bericht wordt alleen verstuurd also één van deze velden gewijzigd wordt:
- `name`, `email`, `phone`, `badge_code`, `role`, `company_id_custom`, `user_id_custom`

---

## 4. Changed and new files

### Nieuw bestand

#### `src/schema/contracts/kassa-user.xsd`
Standalone XSD schema version 1.10.1 for C36/C37/C38.

This schema is separate from the master schema (`kassa-schema-v1.xsd`) because `<UserDeactivated>` conflicts with Contract 22 in the master schema.

Defines:
- `KassaUserCreated` (C36)
- `KassaUserUpdated` (C37)
- `UserDeactivated` (C38)
- `NonEmptyStringType` — prevents empty `<badgeCode>` (minLength=1)

### Gewijzigde bestanden

#### `kassa_pos/utils/rabbitmq_sender.py`

Toegevoegd:
- `USER_TOPIC_EXCHANGE = 'user.topic'`
- Routing key constanten: `ROUTING_KEY_KASSA_USER_CREATED`, `ROUTING_KEY_KASSA_USER_UPDATED`, `ROUTING_KEY_KASSA_USER_DEACTIVATED`
- `_build_kassa_user_created_xml()` — bouwt `<KassaUserCreated>` XML
- `_build_kassa_user_updated_xml()` — bouwt `<KassaUserUpdated>` XML
- `_build_kassa_user_deactivated_xml()` — bouwt `<UserDeactivated>` XML met `<id>` veld
- `_publish_to_topic_exchange()` — publiceert naar `user.topic` zonder consumer-queues te declareren
- `send_kassa_user_created()` — publieke functie voor C36
- `send_kassa_user_updated()` — publieke functie voor C37
- `send_kassa_user_deactivated()` — publieke functie voor C38

#### `kassa_pos/models/res_partner.py`

Toegevoegd:
- `_publish_to_crm()` — roept de CRM sender functies aan
- `unlink()` — vangt email op vóór verwijdering (nodig voor C38)
- `_publish_user_deleted()` — accepteert email parameter en verstuurt C38

Aangepast:
- `_publish_user_change()` — roept nu naast de interne queue ook `_publish_to_crm()` aan
- `_build_user_created_payload_xml()` — produceert `<UserCreated>` (was `<User>`)
- `_build_user_updated_payload_xml()` — produceert `<UserUpdatedIntegration>` (was `<User>`)

#### `src/xml_validator.py`

Toegevoegd:
- `KASSA_USER_SCHEMA_PATH` — pad naar `kassa-user.xsd`
- `_kassa_schema` — geladen standalone schema
- `validate_kassa(xml_string)` — valideert C36/C37/C38 berichten, geeft `(bool, str|None)` terug

#### `setup_rabbitmq.py`

Toegevoegd:
- `user.topic` exchange in de lijst van te declareren exchanges
- Gebruik van omgevingsvariabelen voor verbindingsinstellingen (was hardcoded)

---

## 5. XML Berichten

### C36 — KassaUserCreated

```xml
<KassaUserCreated>
  <userId>550e8400-e29b-41d4-a716-446655440000</userId>
  <firstName>Jan</firstName>
  <lastName>Janssen</lastName>
  <email>jan@example.com</email>
  <companyId>9c21f4e1-8b2e-4d71-a7a2-6f8cbbf81c10</companyId>  <!-- optioneel -->
  <badgeCode>BADGE001</badgeCode>
  <role>CASHIER</role>
  <createdAt>2026-04-29T12:00:00Z</createdAt>
</KassaUserCreated>
```

### C37 — KassaUserUpdated

```xml
<KassaUserUpdated>
  <userId>550e8400-e29b-41d4-a716-446655440000</userId>
  <firstName>Jan</firstName>
  <lastName>Janssen</lastName>
  <email>jan@example.com</email>
  <badgeCode>BADGE001</badgeCode>
  <role>CASHIER</role>
  <updatedAt>2026-04-29T13:00:00Z</updatedAt>
</KassaUserUpdated>
```

### C38 — UserDeactivated

```xml
<UserDeactivated>
  <id>550e8400-e29b-41d4-a716-446655440000</id>
  <email>jan@example.com</email>
  <deactivatedAt>2026-04-29T14:00:00Z</deactivatedAt>
</UserDeactivated>
```

**Let op:** C38 gebruikt `<id>` (niet `<userId>`), conform de afspraak met CRM.

### Toegestane rollen

| Odoo waarde | XML waarde        |
|-------------|-------------------|
| Customer    | VISITOR           |
| Cashier     | CASHIER           |
| Admin       | ADMIN             |

---

## 6. RabbitMQ configuratie

### Exchange declareren

De `user.topic` exchange wordt gedeclareerd door `setup_rabbitmq.py`. Dit script kun je handmatig uitvoeren:

```bash
docker compose exec odoo python3 /app/setup_rabbitmq.py
```

Of voeg hem manueel toe via de RabbitMQ Management UI:
1. Ga naar [http://localhost:15672](http://localhost:15672)
2. Login: `team_kassa` / `kassa_local_dev`
3. Exchanges → Add a new exchange
   - Name: `user.topic`
   - Type: `topic`
   - Durability: Durable

### Verbindingsinstellingen (uit .env)

| Variable         | Waarde       |
|-------------------|--------------|
| `RABBIT_HOST`     | `rabbitmq`   |
| `RABBIT_PORT`     | `5672`       |
| `RABBIT_USER`     | `team_kassa` |
| `RABBIT_PASSWORD` | `kassa_local_dev` |
| `RABBIT_VHOST`    | `/`          |

---

## 7. Hoe het automatisch werkt

1. Beheerder maakt een nieuw contact aan in Odoo met een **User ID** ingevuld
2. Odoo roept `res_partner.create()` aan
3. `_publish_user_change('created')` wordt getriggerd
4. `_publish_to_crm('created', user_data)` roept `send_kassa_user_created()` aan
5. `_publish_to_topic_exchange()` verbindt met RabbitMQ en publiceert het XML-bericht
6. Het bericht staat op de `user.topic` exchange met routing key `kassa.user.created`
7. CRM ontvangt het bericht via hun eigen queue die gebonden is aan `user.topic`

Hetzelfde geldt voor C37 (bij `write()`) en C38 (bij `unlink()`).

---

## 8. Testen

### Handmatige test via terminal

**C36 — Aanmaken:**
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

**C37 — Bijwerken:** vervang `send_kassa_user_created` door `send_kassa_user_updated` en `createdAt` door `updatedAt`.

**C38 — Deactiveren:**
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

### Berichten controleren in RabbitMQ

1. Ga naar [http://localhost:15672](http://localhost:15672) → login also `team_kassa`
2. Maak een testqueue aan: **Queues → Add a new queue** → naam `test.crm.kassa`
3. Bind de queue: klik op de queue → **Bindings → Add binding from exchange**
   - From exchange: `user.topic`
   - Routing key: `kassa.user.*`
4. Stuur een testbericht via het commando hierboven
5. Klik op **Get Message(s)** om het bericht te zien

### Verwachte uitkomst bij succesvolle test

```
Exchange:     user.topic
Routing Key:  kassa.user.created  (of .updated / .deactivated)
Properties:   delivery_mode: 2, content_type: application/xml
Payload:      <KassaUserCreated>...</KassaUserCreated>
```

### Automatische test via contact aanmaken in Odoo

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
        'name': 'Test CRM Gebruiker',
        'email': 'testcrm@test.com',
        'user_id_custom': 'test-crm-uuid-001',
        'badge_code': 'CRM001',
        'role': 'Cashier',
    })
    cr.commit()
    print('Aangemaakt:', partner.id, partner.name)
"
```

### Unit tests (XSD validatie)

```bash
docker compose exec odoo python3 -m pytest src/tests/test_xml_validator.py -v
```

Alle 48 tests moeten slagen, inclusief 12 nieuwe tests voor C36/C37/C38.

---

## 9. Opgeloste bugs

Tijdens de implementatie werden ook de volgende bestaande bugs opgelost:

| Bug | Problem | Oplossing |
|-----|----------|-----------|
| Verkeerde XML elementen | `<User>` werd gebruikt voor zowel create also update | Gesplitst in `<UserCreated>` en `<UserUpdatedIntegration>` |
| Dubbele queue handler | `crm.user.confirmed` stond twee keer in `QUEUE_HANDLERS` waardoor ~50% van de berichten verloren ging | Duplicate verwijderd en handlers samengevoegd |
| Update/delete events niet verwerkt | `on_user_updated` en `on_user_deactivated` logden alleen, maar updaten UserStore niet | `_user_consumer.process_user_message()` toegevoegd |
| `setup_rabbitmq.py` hardcoded credentials | Verbindingsinstellingen stonden hardcoded in het script | Omgevingsvariabelen gebruikt |
| `user.topic` exchange ontbrak | Exchange werd niet automatisch aangemaakt bij opstarten | Toegevoegd aan `setup_rabbitmq.py` |
