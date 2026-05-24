# CRM Team — User Creation Integration with Kassa

## Purpose

This document describes how CRM and Kassa cooperate to create and synchronize users, based on the current implementation and XML contracts.

The content follows the AsyncAPI/XML contract definitions and the code in this repository.

## Summary

The recommended flow is:

1. Kassa publishes a new user profile to the `kassa.user.created` queue as an XML `User`.
2. CRM consumes the message and creates or enriches the user in CRM.
3. CRM publishes a confirmation as XML `UserConfirmed` to the `crm.user.confirmed` queue.
4. Kassa processes `UserConfirmed` and keeps its local user store synchronized.

## RabbitMQ routes

| Direction | Purpose | Exchange | Routing key | Queue | Durable |
|---|---|---|---|---|---|
| Kassa → CRM | User create event | default exchange '' | `kassa.user.created` | `kassa.user.created` | true |
| CRM → Kassa | User confirmation | default exchange '' | `crm.user.confirmed` | `crm.user.confirmed` | true |
| CRM → Kassa | User update | default exchange '' | `crm.user.updated` | `crm.user.updated` | true |
| CRM → Kassa | User deactivated | default exchange '' | `crm.user.deactivated` | `crm.user.deactivated` | true |

Note: messages are published directly to queues using the default exchange; the routing key equals the queue name.


## Step 1 — What CRM receives on user creation

### Message type

Root: `User`

### Queue

`kassa.user.created`

### XML example

```xml
<User>
  <userId>550e8400-e29b-41d4-a716-446655440000</userId>
  <firstName>Jan</firstName>
  <lastName>Peeters</lastName>
  <email>jan@example.com</email>
  <companyId>550e8400-e29b-41d4-a716-446655440001</companyId>
  <badgeCode>QR12345</badgeCode>
  <role>VISITOR</role>
  <createdAt>2026-04-22T10:00:00Z</createdAt>
  <updatedAt>2026-04-22T10:00:00Z</updatedAt>
</User>
```

### Fields

| Field | Required | Description |
|---|---|---|
| `userId` | Yes | UUID v4 unique identifier |
| `firstName` | Yes | First name |
| `lastName` | Yes | Last name |
| `email` | Yes | Email address |
| `companyId` | No | UUID of associated company |
| `badgeCode` | Yes | Badge or QR code identifier |
| `role` | Yes | Role (e.g., VISITOR, CASHIER, ADMIN) |
| `createdAt` | No | ISO 8601 timestamp (UTC) |
| `updatedAt` | No | ISO 8601 timestamp (UTC) |


## Step 2 — What CRM must send back as confirmation

### Message type

Root: `UserConfirmed` (Contract 13)

### Queue

`crm.user.confirmed`

### XML example

```xml
<UserConfirmed>
  <id>550e8400-e29b-41d4-a716-446655440000</id>
  <email>jan@example.com</email>
  <firstName>Jan</firstName>
  <lastName>Peeters</lastName>
  <role>VISITOR</role>
  <isActive>true</isActive>
  <gdprConsent>true</gdprConsent>
  <confirmedAt>2026-04-22T10:00:02Z</confirmedAt>
</UserConfirmed>
```

### Contract rules

| Field | Required |
|---|---|
| `id` | Yes |
| `email` | Yes |
| `firstName` | Yes |
| `lastName` | Yes |
| `role` | Yes |
| `isActive` | Yes |
| `gdprConsent` | Yes |
| `confirmedAt` | Yes |
| `phone` | No |
| `companyId` | No |
| `badgeCode` | No |

Important:

- `id` must match the `userId` from the `User` message.
- `role` must be a valid enum defined by the contract.
- `confirmedAt` must be an ISO 8601 UTC timestamp (for example: 2026-04-22T10:00:02Z).


## Field mapping: Kassa `User` → CRM `UserConfirmed`

| Kassa `User` | CRM `UserConfirmed` | Notes |
|---|---|---|
| `userId` | `id` | Must remain identical across lifecycle |
| `firstName` | `firstName` | 1:1 mapping |
| `lastName` | `lastName` | 1:1 mapping |
| `email` | `email` | 1:1 mapping |
| `role` | `role` | Must be contract-compatible |
| `companyId` | `companyId` | Optional |
| `badgeCode` | `badgeCode` | Optional in `UserConfirmed` but recommended for POS sync |
| `createdAt` | `confirmedAt` | `confirmedAt` reflects CRM confirmation time |


## Recommended end-to-end flow

1. Consume `kassa.user.created`.
2. Validate XML and required fields.
3. Create or update the user in CRM.
4. Publish `UserConfirmed` to `crm.user.confirmed`.
5. For updates, publish `UserUpdated` to `crm.user.updated`.
6. For deactivations or GDPR actions, publish `UserDeactivated` to `crm.user.deactivated`.

## Idempotency and retries

### Idempotency

Use `id`/`userId` as the idempotency key in CRM to ensure duplicate deliveries do not create duplicate users.

### Retry behaviour

If Kassa temporarily cannot publish, Kassa stores messages in a local fallback queue in Odoo. When CRM recovers, pending messages can be re-sent. Idempotency prevents duplicate creation.

## Minimal consumer/publisher examples

### Consume `kassa.user.created`

```python
channel.queue_declare(queue='kassa.user.created', durable=True)
channel.basic_consume(queue='kassa.user.created', on_message_callback=on_user, auto_ack=True)
```

### Publish `UserConfirmed`

```python
channel.queue_declare(queue='crm.user.confirmed', durable=True)
channel.basic_publish(
  exchange='',
  routing_key='crm.user.confirmed',
  body=user_confirmed_xml.encode('utf-8')
)
```

## Validation sources

Use these files as sources of truth:

- `src/schema/kassa-schema-v1.xsd`
- `src/tests/test_xml_validator.py`
- `src/messaging/user_consumer.py`
- `kassa_pos/models/user_registration.py`

## Interoperability checklist

- Queue `kassa.user.created` exists and is durable.
- Queue `crm.user.confirmed` exists and is durable.
- CRM replies with a valid `UserConfirmed` XML (not free-form XML).
- `id` in `UserConfirmed` equals `userId` from `User`.
- XML timestamps are ISO 8601 UTC with `Z` suffix.
- CRM processes duplicate deliveries idempotently.

## Troubleshooting

### User does not appear in Kassa after creation

Check:

1. Was `UserConfirmed` published to `crm.user.confirmed`?
2. Is the XML valid against `kassa-schema-v1.xsd`?
3. Is `id` a valid UUID v4?
4. Is `role` a valid enum value?

### `User` did not reach CRM

Check:

1. Queue `kassa.user.created` exists.
2. CRM consumer is connected with correct vhost/credentials.
3. RabbitMQ queue durability is configured correctly.
4. Odoo fallback queue contains pending messages (in case of temporary outage).
