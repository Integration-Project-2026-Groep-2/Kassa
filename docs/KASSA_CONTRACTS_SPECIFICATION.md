# Kassa Contracts — RabbitMQ Integration Specification
## All RabbitMQ contracts maintained by Team Kassa
Integration Project 2025/2026 | Group 2
Author: Team Kassa | Version: 1.0 | May 2026

---

## Quick Reference — Contract overview

### Release 1 (R1)
| Contract | Direction | Exchange / Routing Key | Durable | Essential? |
|---|---|---|---|---|
| **C7** | Kassa → Controlroom | `heartbeat.direct` / routing key (env: `HEARTBEAT_ROUTING_KEY`) | exchange: true | ✅ |
| **C8** | Kassa → Controlroom | `statuscheck.direct` / routing key (see config) | exchange: true | ✅ |
| **C10a** | Kassa → CRM | `user.topic` / `kassa.person.lookup.requested` (topic) | exchange: true | ✅ |
| **K-01** | Kassa → Invoicing | `kassa.topic` / `kassa.invoice.requested` (topic) | exchange: true | ✅ |

---

## Release 1 — Core Contracts

### Contract C7 — Heartbeat (Kassa → Controlroom)

**Exchange:** `heartbeat.direct` (publisher) — consumers bind a queue to this exchange with a routing key. The default routing key and queue names are configurable via environment variables (`HEARTBEAT_ROUTING_KEY`, `HEARTBEAT_QUEUE`).

**Exchange durability:** `heartbeat.direct` is declared durable in setup scripts (see `setup_rabbitmq.py`). Queue durability is consumer-side and therefore not enforced here; configure consumer queues as durable if you need persisted heartbeats.

**Default frequency:** controlled by `HEARTBEAT_INTERVAL_SECONDS` (default `1` in `.env`). The interval is configurable and a higher value (e.g., 5–30s) is recommended for production to reduce load.

Kassa publishes a lightweight heartbeat so Controlroom can detect whether the Kassa service is running. The message schema and validations are enforced by the XSDs and unit tests in `src/tests/`.

---

Refer to `src/schema/` for the canonical XSDs used by each contract. Also see `docs/XSD_SCHEMA_DOCUMENTATION.md` for a high-level schema overview.

---

## Additional Contracts (K-02 and User CRUD)

### Contract K-02 — BatchClosed (Daily Batch)

**Purpose:** End-of-day batch containing invoice-eligible orders grouped per user for the invoicing system.

**Exchange:** `kassa.topic`  
**Routing key:** `kassa.closed`  
**Consumer-side queue:** bind a durable queue (e.g. `facturatie.kassa.batch.closed`) to `kassa.topic` with routing key `kassa.closed`.

**Durable:** true (publisher must ensure idempotency via `batchId`).

**Schema:** `src/schema/kassa_batch_contract.xsd` — contains `BatchClosed` root with `batchId`, `closedAt`, `currency`, optional `users` array and a `summary`.

**Example payload (abridged):**

```xml
<BatchClosed>
	<batchId>4e7f0c4b-3d86-4e9d-9b4f-6d8e2a1d1a11</batchId>
	<closedAt>2026-04-18T18:30:00Z</closedAt>
	<currency>EUR</currency>
	<users>
		<user>
			<userId>550e8400-e29b-41d4-a716-446655440000</userId>
			<items>
				<item>
					<productName>Bier</productName>
					<quantity>2</quantity>
					<unitPrice>3.50</unitPrice>
					<totalPrice>7.00</totalPrice>
				</item>
			</items>
			<totalAmount>7.00</totalAmount>
		</user>
	</users>
	<summary>
		<totalOrders>1</totalOrders>
		<totalAmount>7.00</totalAmount>
	</summary>
</BatchClosed>
```

**Implementation references:**
- Schema: `src/schema/kassa_batch_contract.xsd`
- Publisher: `kassa_pos/services/pos_batch_service.py`
- Sender helper: `kassa_pos/utils/rabbitmq_sender.py`

---

### Contracts C36–C38 — User CRUD (Kassa → CRM / CRM → Kassa)

These contracts are defined in `src/schema/contracts/kassa-user.xsd` and are used for user lifecycle events between Kassa and CRM.

#### C36 — `KassaUserCreated` (Kassa → CRM)

- **Purpose:** Kassa publishes a newly-created or registered user for CRM to consume and create a corresponding CRM user.
- **Exchange:** `user.topic`  
- **Routing key:** `kassa.user.created`  
- **Queue (example):** `crm.kassa.user.created` (durable)
- **Schema:** `src/schema/contracts/kassa-user.xsd` — `KassaUserCreated` element contains `userId`, `firstName`, `lastName`, `email`, optional `companyId`, `badgeCode`, `role`, timestamps.

#### C37 — `KassaUserUpdated` (Kassa → CRM)

- **Purpose:** Notify CRM that an existing user has been updated in Kassa (e.g., badge change, name, company link).
- **Exchange:** `user.topic`  
- **Routing key:** `kassa.user.updated`  
- **Queue (example):** `crm.kassa.user.updated` (durable)

#### C38 — `UserDeactivated` (CRM → Kassa)

- **Purpose:** CRM notifies Kassa about user deactivation (GDPR or admin action). Note: Kassa typically consumes this; Kassa does not publish C38.
- **Exchange:** `user.topic`  
- **Routing key:** `kassa.user.deactivated`  
- **Queue (example):** `crm.kassa.user.deactivated` (durable)

**Implementation references:**
- Schema: `src/schema/contracts/kassa-user.xsd`
- Kassa publisher: `kassa_pos/models/user_registration.py` and `kassa_pos/utils/rabbitmq_sender.py`
- Kassa consumer handling deactivations: `src/main_receiver.py`

**Retry / Dead-letter topology:**
- The system declares `user.retry` and `user.dlx` exchanges and related retry TTLs for user event processing (see `setup_rabbitmq.py`).
- Environment variables `USER_EVENTS_RETRY_EXCHANGE` and `USER_EVENTS_RETRY_TTL_MS` control retry exchange name and TTL (default 15000 ms). Consumers/publishers should respect this retry topology for resilient processing.

