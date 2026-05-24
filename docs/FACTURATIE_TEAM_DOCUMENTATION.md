# Invoicing Team - XML and RabbitMQ Documentation

## Purpose

This page describes which XML messages Kassa sends to the Invoicing and related systems, which RabbitMQ exchange/queue/routing key is used, and how the payloads are structured.

In RabbitMQ terms: a `channel` is the technical session inside the connection. For Invoicing the `exchange`, `queue` and `routing key` are most relevant, as they determine where messages end up.

## Samenvatting

| Message | Purpose | RabbitMQ route | XML root |
|---|---|---|---|
| `PaymentConfirmed` | Confirm payment towards CRM | Default exchange `''` -> queue `kassa.payment.confirmed` | `<PaymentConfirmed>` |
| `InvoiceRequested` | Invoice request for business order | Default exchange `''` -> queue `kassa.invoice.requested` | `<InvoiceRequested>` |
| `BatchClosed` | End-of-day batch with invoice orders | Exchange `kassa.topic` -> routing key `kassa.closed` | `<BatchClosed>` |

## 1. PaymentConfirmed

### When is this sent?

When a POS order is processed as paid. In the current implementation the system will attempt to send this for paid orders as long as an email address is available.

### RabbitMQ route

- Exchange: default exchange `''`
- Routing key: `kassa.payment.confirmed`
- Queue: `kassa.payment.confirmed`
- Type: durable queue

### XML structure

Root element: `<PaymentConfirmed>`

#### Fields

| Field | Required | Description |
|---|---|---|
| `userId` | No | Internal UUID of the user |
| `email` | Yes | Customer email address |
| `registrationId` | No | Registration id if available |
| `amount` | Yes | Paid amount |
| `currency` | Yes | Always `EUR` |
| `paidAt` | Yes | ISO 8601 timestamp |

### Example

```xml
<PaymentConfirmed>
    <userId>550e8400-e29b-41d4-a716-446655440000</userId>
    <email>klant@example.com</email>
    <registrationId>REG-12345</registrationId>
    <amount>12.50</amount>
    <currency>EUR</currency>
    <paidAt>2026-04-18T10:00:00Z</paidAt>
</PaymentConfirmed>
```

### Implementatie

- Builder: [src/messaging/message_builders.py](../src/messaging/message_builders.py)
- Sender: [kassa_pos/utils/rabbitmq_sender.py](../kassa_pos/utils/rabbitmq_sender.py)
- Trigger: [kassa_pos/models/pos_order.py](../kassa_pos/models/pos_order.py)

## 2. InvoiceRequested

### Wanneer wordt dit verstuurd?

Alleen voor orders met `paymentType = Invoice` en wanneer de klant aan een bedrijf gekoppeld is.

Dit bericht is bedoeld voor het facturatieproces.

### RabbitMQ route

- Exchange: standaard exchange `''`
- Routing key: `kassa.invoice.requested`
- Queue: `kassa.invoice.requested`
- Type: durable queue

Technisch gezien publiceert Kassa direct naar de queue via de default exchange. De queue-naam en routing key zijn dus gelijk.

### XML-structuur

Root element: `<InvoiceRequested>`

#### Velden

| Veld | Verplicht | Omschrijving |
|---|---|---|
| `orderId` | Ja | UUID van de POS-order |
| `userId` | Ja | UUID van de gebruiker |
| `companyId` | Ja | UUID van het bedrijf |
| `amount` | Ja | Totaalbedrag van de order |
| `currency` | Ja | Altijd `EUR` |
| `orderedAt` | Ja | ISO 8601 timestamp |
| `items` | Ja | Lijst met orderregels |
| `email` | Nee | E-mailadres van de klant |
| `companyName` | Nee | Naam van het bedrijf |
| `eventId` | Nee | Event- of context-id indien gebruikt |
| `paymentReference` | Nee | Betaalreferentie indien beschikbaar |

### XML for items

Each order line contains:

| Field | Required | Description |
|---|---|---|
| `productName` | Yes | Product name |
| `quantity` | Yes | Quantity |
| `unitPrice` | Yes | Price per unit |

### Example

```xml
<InvoiceRequested>
    <orderId>order-001</orderId>
    <userId>550e8400-e29b-41d4-a716-446655440000</userId>
    <companyId>550e8400-e29b-41d4-a716-446655440001</companyId>
    <amount>49.99</amount>
    <currency>EUR</currency>
    <orderedAt>2026-04-18T10:00:00Z</orderedAt>
    <items>
        <item>
            <productName>Beer</productName>
            <quantity>2</quantity>
            <unitPrice>3.50</unitPrice>
        </item>
        <item>
            <productName>SoftDrink</productName>
            <quantity>3</quantity>
            <unitPrice>2.25</unitPrice>
        </item>
    </items>
    <email>invoicing@example.com</email>
    <companyName>Company Ltd</companyName>
</InvoiceRequested>
```

### Implementation

- Builder: [src/messaging/message_builders.py](../src/messaging/message_builders.py)
- Sender: [kassa_pos/utils/rabbitmq_sender.py](../kassa_pos/utils/rabbitmq_sender.py)
- Trigger: [kassa_pos/models/pos_order.py](../kassa_pos/models/pos_order.py)

## 3. BatchClosed

### When is this sent?

When closing the POS session via the closing button.

The batch contains only orders that meet:

- `paymentType = Invoice`
- identified customer with a UUID

### RabbitMQ route

- Exchange: `kassa.topic`
- Routing key: `kassa.closed`
- Queue: consumer-side queue that binds to `kassa.closed`
- Type: durable queue

Important: the publisher sends to the exchange `kassa.topic`. The Invoicing consumer must therefore bind a queue on this exchange with routing key `kassa.closed`.

### XML structure

Root element: `<BatchClosed>`

#### Main elements

| Field | Required | Description |
|---|---|---|
| `batchId` | Yes | UUID of the batch |
| `closedAt` | Yes | ISO 8601 timestamp |
| `currency` | Yes | Always `EUR` |
| `users` | No | Grouped orders per user |
| `summary` | Yes | Summary of the batch |

#### `users` structure

Each user contains:

| Field | Required | Description |
|---|---|---|
| `userId` | Yes | UUID of the user |
| `items` | Yes | All order lines for that user |
| `totalAmount` | Yes | Total per user |

Each item contains:

| Field | Required | Description |
|---|---|---|
| `productName` | Yes | Product name |
| `quantity` | Yes | Quantity |
| `unitPrice` | Yes | Unit price, 2 decimals |
| `totalPrice` | Yes | Line total, 2 decimals |

#### `summary` structure

| Field | Required | Description |
|---|---|---|
| `totalOrders` | Ja | Aantal orders in de batch |
| `totalAmount` | Ja | Totaalbedrag van de batch |
| `orderIds` | Nee | Lijst van order UUIDs |

### Voorbeeld

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
        <orderIds>
            <orderId>550e8400-e29b-41d4-a716-446655440000</orderId>
        </orderIds>
    </summary>
</BatchClosed>
```

### Implementatie

- Builder: [src/messaging/message_builders.py](../src/messaging/message_builders.py)
- Service: [kassa_pos/services/pos_batch_service.py](../kassa_pos/services/pos_batch_service.py)
- Trigger: [kassa_pos/models/pos_order.py](../kassa_pos/models/pos_order.py)
- Schema: [src/schema/kassa-closed-batch.xsd](../src/schema/kassa_batch_contract.xsd)

## RabbitMQ topology

### Exchanges

| Exchange | Type | Doel |
|---|---|---|
| `kassa.topic` | topic | Dagafsluiting / batch closing |
| `user.direct` | direct | User CRUD events |
| `user.dlx` | direct | Dead-letter exchange voor user events |
| `user.retry` | direct | Retry flow voor user events |
| `heartbeat.direct` | direct | Heartbeat messages |

### Queues voor facturatie

| Queue | Type | Omschrijving |
|---|---|---|
| `kassa.payment.confirmed` | durable | Betalingsbevestigingen richting CRM |
| `kassa.invoice.requested` | durable | Factuurverzoeken voor facturatie |
| `kassa.closed` | durable | Batch closure berichten via `kassa.topic` |

### Routing keys

| Routing key | Exchange | Omschrijving |
|---|---|---|
| `kassa.payment.confirmed` | default exchange `''` | Betaling bevestigd |
| `kassa.invoice.requested` | default exchange `''` | Factuurverzoek |
| `kassa.closed` | `kassa.topic` | Dagafsluitbatch |

## Wat facturatie moet consumeren

Also team facturatie hoef je in principe deze stromen te consumeren:

1. `kassa.invoice.requested`
2. `kassa.closed` via binding op `kassa.topic` met routing key `kassa.closed`

`kassa.payment.confirmed` is vooral CRM-gerelateerd, maar staat hier vermeld omdat het in dezelfde XML- en RabbitMQ-implementatie zit.

## Voorbeeld consumer binding

```python
channel.exchange_declare(exchange='kassa.topic', exchange_type='topic', durable=True)
channel.queue_declare(queue='facturatie.queue', durable=True)
channel.queue_bind(
    queue='facturatie.queue',
    exchange='kassa.topic',
    routing_key='kassa.closed'
)
```

Voor invoice requests via default exchange:

```python
channel.queue_declare(queue='kassa.invoice.requested', durable=True)
channel.basic_consume(queue='kassa.invoice.requested', on_message_callback=callback, auto_ack=True)
```

## Validatie

De XML-berichten worden ook gevalideerd tegen schema’s en tests:

- [src/schema/kassa-schema-v1.xsd](../src/schema/kassa-schema-v1.xsd)
- [src/schema/kassa-closed-batch.xsd](../src/schema/kassa_batch_contract.xsd)
- [src/tests/test_xml_validator.py](../src/tests/test_xml_validator.py)

## Praktische afspraken

- XML is UTF-8
- Velden met datums/tijden gebruiken ISO 8601: `YYYY-MM-DDTHH:MM:SSZ`
- Bedragen worden also numerieke waarden verstuurd, in euro (`EUR`)
- RabbitMQ queues zijn durable tenzij anders vermeld
- Facturatie moet idempotent verwerken op basis van `orderId` of `batchId`

## Relevant bronbestanden

- [kassa_pos/utils/rabbitmq_sender.py](../kassa_pos/utils/rabbitmq_sender.py)
- [kassa_pos/models/pos_order.py](../kassa_pos/models/pos_order.py)
- [kassa_pos/services/pos_batch_service.py](../kassa_pos/services/pos_batch_service.py)
- [src/messaging/message_builders.py](../src/messaging/message_builders.py)
- [src/config.py](../src/settings.py)
- [RABBITMQ_SETUP.md](RABBITMQ_SETUP.md)
