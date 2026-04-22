# CRM Team - User Creation Integratie met Kassa

## Doel

Deze documentatie beschrijft hoe CRM en Kassa samen een gebruiker aanmaken op basis van de huidige implementatie en XML-contracten.

De inhoud is afgestemd op de contracten in AsyncAPI/XML v1.8.0 en op de bestaande code in deze repository.

## Korte samenvatting

Voor een correcte samenwerking gebruik je dit patroon:

1. Kassa publiceert een nieuw user-profiel op queue integration.user.created als XML User.
2. CRM consumeert dit bericht en maakt of verrijkt de gebruiker in CRM.
3. CRM publiceert daarna een bevestiging op queue crm.user.confirmed als XML UserConfirmed.
4. Kassa verwerkt UserConfirmed en houdt de lokale user-store synchroon.

## RabbitMQ routes

| Richting | Doel | Exchange | Routing key | Queue | Durable |
|---|---|---|---|---|---|
| Kassa -> CRM | User create event | default exchange '' | integration.user.created | integration.user.created | true |
| CRM -> Kassa | User bevestigd | default exchange '' | crm.user.confirmed | crm.user.confirmed | true |
| CRM -> Kassa | User update | default exchange '' | crm.user.updated | crm.user.updated | true |
| CRM -> Kassa | User deactivated | default exchange '' | crm.user.deactivated | crm.user.deactivated | true |

Opmerking:
In deze flow worden berichten direct op queues gepubliceerd via de default exchange. Routing key en queue-naam zijn dus gelijk.

## Stap 1 - Wat CRM ontvangt bij user-aanmaak

### Berichttype

Root: User

### Queue

integration.user.created

### XML formaat (voorbeeld)

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

### Velden

| Veld | Verplicht | Beschrijving |
|---|---|---|
| userId | Ja | UUID v4 |
| firstName | Ja | Voornaam |
| lastName | Ja | Achternaam |
| email | Ja | E-mail |
| companyId | Nee | UUID van bedrijf |
| badgeCode | Ja | Badge/QR code |
| role | Ja | Rol (bijv. VISITOR, CASHIER, ADMIN) |
| createdAt | Nee | ISO 8601 |
| updatedAt | Nee | ISO 8601 |

## Stap 2 - Wat CRM moet terugsturen als bevestiging

### Berichttype

Root: UserConfirmed (Contract 13)

### Queue

crm.user.confirmed

### XML formaat (voorbeeld)

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

### Contractregels

| Veld | Verplicht |
|---|---|
| id | Ja |
| email | Ja |
| firstName | Ja |
| lastName | Ja |
| role | Ja |
| isActive | Ja |
| gdprConsent | Ja |
| confirmedAt | Ja |
| phone | Nee |
| companyId | Nee |
| badgeCode | Nee |

Belangrijk:
- id moet dezelfde UUID zijn als userId uit het User-bericht.
- role moet een geldige contractwaarde zijn.
- confirmedAt moet ISO 8601 UTC zijn, bijvoorbeeld 2026-04-22T10:00:02Z.

## Mapping tussen Kassa User en CRM UserConfirmed

| Kassa User | CRM UserConfirmed | Opmerking |
|---|---|---|
| userId | id | Moet identiek blijven |
| firstName | firstName | 1-op-1 |
| lastName | lastName | 1-op-1 |
| email | email | 1-op-1 |
| role | role | Moet contract-compatibel zijn |
| companyId | companyId | Optioneel |
| badgeCode | badgeCode | Optioneel in UserConfirmed, maar aanbevolen |
| createdAt | confirmedAt | confirmedAt is CRM-confirmatiemoment |

## Aanbevolen end-to-end flow

1. Consumeer integration.user.created.
2. Valideer XML en verplichte velden.
3. Maak user in CRM (of update als user al bestaat).
4. Publiceer UserConfirmed naar crm.user.confirmed.
5. Voor latere wijzigingen publiceer UserUpdated naar crm.user.updated.
6. Voor GDPR/non-actief publiceer UserDeactivated naar crm.user.deactivated.

## Idempotentie en retries

### Idempotentie

Gebruik id/userId als idempotency key in CRM, zodat dubbele delivery geen dubbele users maakt.

### Retrygedrag

Als Kassa tijdelijk niet kan publiceren, wordt een lokale fallback queue gebruikt in Odoo. Daardoor kunnen create-events later alsnog binnenkomen.

## Minimale consumer/publisher voorbeelden

### Consume integration.user.created

```python
channel.queue_declare(queue='integration.user.created', durable=True)
channel.basic_consume(queue='integration.user.created', on_message_callback=on_user, auto_ack=True)
```

### Publish UserConfirmed

```python
channel.queue_declare(queue='crm.user.confirmed', durable=True)
channel.basic_publish(
    exchange='',
    routing_key='crm.user.confirmed',
    body=user_confirmed_xml.encode('utf-8')
)
```

## Validatiebronnen

Gebruik deze bestanden als bron van waarheid:

- src/schema/kassa-schema-v1.xsd
- src/tests/test_xml_validator.py
- src/messaging/user_consumer.py
- kassa_pos/models/user_registration.py

## Interoperability checklist

- Queue integration.user.created bestaat en is durable.
- Queue crm.user.confirmed bestaat en is durable.
- CRM antwoordt met UserConfirmed (niet met vrij formaat XML).
- id in UserConfirmed equals userId uit User.
- XML timestamps zijn ISO 8601 UTC met Z suffix.
- CRM verwerkt duplicate deliveries idempotent.

## Troubleshooting

### User komt niet aan in Kassa na create

Controleer:

1. Werd UserConfirmed gepubliceerd op crm.user.confirmed.
2. Is XML geldig tegen kassa-schema-v1.xsd.
3. Is id een geldige UUID v4.
4. Is role een geldige enumwaarde.

### UserCreated komt niet aan in CRM

Controleer:

1. Queue integration.user.created bestaat.
2. CRM-consumer is verbonden met juiste vhost/credentials.
3. RabbitMQ durable queue-instellingen zijn correct.
4. Odoo fallback queue heeft pending berichten (bij tijdelijke outage).
