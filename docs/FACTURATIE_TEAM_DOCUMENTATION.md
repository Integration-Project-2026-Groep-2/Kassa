# Facturatie Team - XML en RabbitMQ Documentatie

## Doel

Deze pagina beschrijft welke XML-berichten Kassa verstuurt richting facturatie en gerelateerde systemen, via welke RabbitMQ exchange/queue/routing key dat gebeurt, en hoe de payloads zijn opgebouwd.

In RabbitMQ-termen: een `channel` is de technische sessie binnen de verbinding. Voor facturatie zijn vooral de `exchange`, `queue` en `routing key` relevant, omdat die bepalen waar berichten terechtkomen.

## Samenvatting

| Bericht | Doel | RabbitMQ route | XML root |
|---|---|---|---|
| `PaymentConfirmed` | Betaling bevestigen richting CRM | Default exchange `''` -> queue `kassa.payment.confirmed` | `<PaymentConfirmed>` |
| `InvoiceRequested` | Factuurverzoek voor zakelijke order | Default exchange `''` -> queue `kassa.invoice.requested` | `<InvoiceRequested>` |
| `BatchClosed` | Dagafsluiting met alle invoice-orders | Exchange `kassa.topic` -> routing key `kassa.closed` | `<BatchClosed>` |

## 1. PaymentConfirmed

### Wanneer wordt dit verstuurd?

Wanneer een POS-order als betaald wordt verwerkt. In de huidige implementatie wordt dit altijd geprobeerd voor betaalde orders, zolang er een e-mailadres aanwezig is.

### RabbitMQ route

- Exchange: standaard exchange `''`
- Routing key: `kassa.payment.confirmed`
- Queue: `kassa.payment.confirmed`
- Type: durable queue

### XML-structuur

Root element: `<PaymentConfirmed>`

#### Velden

| Veld | Verplicht | Omschrijving |
|---|---|---|
| `userId` | Nee | Interne UUID van de gebruiker |
| `email` | Ja | E-mailadres van de klant |
| `registrationId` | Nee | Registratie-id indien beschikbaar |
| `amount` | Ja | Betaald bedrag |
| `currency` | Ja | Altijd `EUR` |
| `paidAt` | Ja | ISO 8601 timestamp |

### Voorbeeld

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

- Builder: [src/messaging/message_builders.py](src/messaging/message_builders.py)
- Sender: [kassa_pos/utils/rabbitmq_sender.py](kassa_pos/utils/rabbitmq_sender.py)
- Trigger: [kassa_pos/models/pos_order.py](kassa_pos/models/pos_order.py)

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

### XML voor items

Elke orderregel bevat:

| Veld | Verplicht | Omschrijving |
|---|---|---|
| `productName` | Ja | Naam van het product |
| `quantity` | Ja | Aantal |
| `unitPrice` | Ja | Prijs per stuk |

### Voorbeeld

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
            <productName>Bier</productName>
            <quantity>2</quantity>
            <unitPrice>3.50</unitPrice>
        </item>
        <item>
            <productName>Frisdrank</productName>
            <quantity>3</quantity>
            <unitPrice>2.25</unitPrice>
        </item>
    </items>
    <email>facturatie@example.com</email>
    <companyName>Bedrijf NV</companyName>
</InvoiceRequested>
```

### Implementatie

- Builder: [src/messaging/message_builders.py](src/messaging/message_builders.py)
- Sender: [kassa_pos/utils/rabbitmq_sender.py](kassa_pos/utils/rabbitmq_sender.py)
- Trigger: [kassa_pos/models/pos_order.py](kassa_pos/models/pos_order.py)

## 3. BatchClosed

### Wanneer wordt dit verstuurd?

Bij het afsluiten van de POS-sessie via de afsluitknop.

De batch bevat alleen orders die voldoen aan:

- `paymentType = Invoice`
- geïdentificeerde klant met een UUID

### RabbitMQ route

- Exchange: `kassa.topic`
- Routing key: `kassa.closed`
- Queue: consumer-side queue die bindt op `kassa.closed`
- Type: durable queue

Belangrijk: de publisher stuurt naar de exchange `kassa.topic`. Facturatie moet daarom een queue binden op deze exchange met routing key `kassa.closed`.

### XML-structuur

Root element: `<BatchClosed>`

#### Hoofdelementen

| Veld | Verplicht | Omschrijving |
|---|---|---|
| `batchId` | Ja | UUID van de batch |
| `closedAt` | Ja | ISO 8601 timestamp |
| `currency` | Ja | Altijd `EUR` |
| `users` | Nee | Gegroepeerde orders per gebruiker |
| `summary` | Ja | Samenvatting van de batch |

#### `users` structuur

Elke user bevat:

| Veld | Verplicht | Omschrijving |
|---|---|---|
| `userId` | Ja | UUID van de gebruiker |
| `items` | Ja | Alle orderregels voor die gebruiker |
| `totalAmount` | Ja | Totaal per gebruiker |

Elke item bevat:

| Veld | Verplicht | Omschrijving |
|---|---|---|
| `productName` | Ja | Productnaam |
| `quantity` | Ja | Aantal |
| `unitPrice` | Ja | Stukprijs, 2 decimalen |
| `totalPrice` | Ja | Regelbedrag, 2 decimalen |

#### `summary` structuur

| Veld | Verplicht | Omschrijving |
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

- Builder: [src/messaging/message_builders.py](src/messaging/message_builders.py)
- Service: [kassa_pos/services/pos_batch_service.py](kassa_pos/services/pos_batch_service.py)
- Trigger: [kassa_pos/models/pos_order.py](kassa_pos/models/pos_order.py)
- Schema: [src/schema/kassa-closed-batch.xsd](src/schema/kassa-closed-batch.xsd)

## RabbitMQ topologie

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

Als team facturatie hoef je in principe deze stromen te consumeren:

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

- [src/schema/kassa-schema-v1.xsd](src/schema/kassa-schema-v1.xsd)
- [src/schema/kassa-closed-batch.xsd](src/schema/kassa-closed-batch.xsd)
- [src/tests/test_xml_validator.py](src/tests/test_xml_validator.py)

## Praktische afspraken

- XML is UTF-8
- Velden met datums/tijden gebruiken ISO 8601: `YYYY-MM-DDTHH:MM:SSZ`
- Bedragen worden als numerieke waarden verstuurd, in euro (`EUR`)
- RabbitMQ queues zijn durable tenzij anders vermeld
- Facturatie moet idempotent verwerken op basis van `orderId` of `batchId`

## Relevante bronbestanden

- [kassa_pos/utils/rabbitmq_sender.py](kassa_pos/utils/rabbitmq_sender.py)
- [kassa_pos/models/pos_order.py](kassa_pos/models/pos_order.py)
- [kassa_pos/services/pos_batch_service.py](kassa_pos/services/pos_batch_service.py)
- [src/messaging/message_builders.py](src/messaging/message_builders.py)
- [src/config.py](src/config.py)
- [RABBITMQ_SETUP.md](RABBITMQ_SETUP.md)
