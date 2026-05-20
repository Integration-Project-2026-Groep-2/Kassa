# Kassa Contracten — RabbitMQ Integration Specification
## Alle RabbitMQ-contracten van Team Kassa
Integration Project 2025/2026 | Groep 2  
Auteur: Team Kassa | Versie: 1.0 | Mei 2026

---

## Quick Reference — Contractoverzicht

### Release 1 (R1)
| Contract | Richting | Queue | Durable | Essentieel? |
|---|---|---|---|---|
| **C7** | Kassa → Controlroom | `kassa.heartbeat` | false | ✅ |
| **C8** | Kassa → Controlroom | `kassa.status.checked` | false | ✅ |
| **C9** | Controlroom → Kassa | `controlroom.warning.issued` | false | ⚠️ |
| **C10a** | Kassa → CRM | `kassa.person.lookup.requested` | true | ✅ |
| **C10b** | CRM → Kassa | `crm.person.lookup.responded` | false | ✅ |
| **C13** | CRM → Kassa | `crm.user.confirmed` | true | ✅ |
| **C14** | CRM → Kassa | `crm.company.confirmed` | true | ✅ |
| **C16** | Kassa → CRM | `kassa.payment.confirmed` | true | ✅ |
| **C17a** | Kassa → CRM | `kassa.unpaid.requested` | true | ✅ |
| **C17b** | CRM → Kassa | `crm.unpaid.responded` | false | ✅ |
| **K-01** | Kassa → Facturatie | `kassa.invoice.requested` | true | ✅ |

### Release 2 (R2)
| Contract | Richting | Queue | Durable |
|---|---|---|---|
| **C18** | CRM → Kassa | `crm.user.updated` | true |
| **C19** | CRM → Kassa | `crm.company.updated` | true |

### Release 3 (R3)
| Contract | Richting | Queue | Durable |
|---|---|---|---|
| **C22** | CRM → Kassa | `crm.user.deactivated` | true |
| **C23** | CRM → Kassa | `crm.company.deactivated` | true |

---

## Release 1 — Kern Contracten

### Contract C7 — Heartbeat (Kassa → Controlroom)

**Queue:** `kassa.heartbeat` | **Durable:** false  
**Frequentie:** Elke seconde  
**Relatie:** US-25, US-26

Kassa publiceert een lichtgewicht heartbeat zodat Controlroom kan detecteren of het kassasysteem nog draait.

**XML Root:** `<Heartbeat>`

**Verplichte velden:**
- `serviceId` — altijd waarde `KASSA`
- `timestamp` — ISO 8601 (bijv. `2026-05-13T14:30:45Z`)

**Voorbeeld:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Heartbeat>
  <serviceId>KASSA</serviceId>
  <timestamp>2026-05-13T14:30:45Z</timestamp>
</Heartbeat>
```

**Opmerking:**
- Geen extra velden toegestaan
- Dit contract moet zo licht mogelijk blijven voor minimalere overhead

---

### Contract C8 — Status Check (Kassa → Controlroom)

**Queue:** `kassa.status.checked` | **Durable:** false  
**Frequentie:** Elke 30 seconden (voorstel)  
**Relatie:** US-25

Uitgebreidere gezondheidscheck dan de heartbeat. Bevat runtime-status en systeembelasting.

**XML Root:** `<StatusCheck>`

**Verplichte velden:**
- `serviceId` — `KASSA`
- `timestamp` — ISO 8601
- `status` — enum: `healthy` | `degraded` | `unhealthy` | `unknown`
- `uptime` — seconden sinds container-start (integer)
- `systemLoad` — complex type met:
  - `cpu` — float 0.0–1.0
  - `memory` — float 0.0–1.0
  - `disk` — float 0.0–1.0

**Voorbeeld:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<StatusCheck>
  <serviceId>KASSA</serviceId>
  <timestamp>2026-05-13T14:30:45Z</timestamp>
  <status>healthy</status>
  <uptime>86400</uptime>
  <systemLoad>
    <cpu>0.45</cpu>
    <memory>0.62</memory>
    <disk>0.78</disk>
  </systemLoad>
</StatusCheck>
```

---

### Contract C9 — System Warning (Controlroom → Kassa)

**Queue:** `controlroom.warning.issued` | **Durable:** false  
**Relatie:** US-26

Controlroom stuurt een waarschuwing naar Kassa. Kassa logt dit en crasht nooit.

**XML Root:** `<Warning>`

**Verplichte velden:**
- `serviceId` — identificatie van de bron (bijv. `CONTROLROOM`)
- `message` — tekstuele waarschuwing
- `type` — enum: `heartbeat` | `statusCheck` | `user`

**Consumer-gedrag in Kassa:**
- Loggen als error of warning (afhankelijk van severity)
- Nooit crashen op ontvangst
- Nooit de POS-flow blokkeren

---

### Contract C10a — Person Lookup Request (Kassa → CRM)

**Queue:** `kassa.person.lookup.requested` | **Durable:** true  
**Relatie:** US-47

Kassa vraagt aan CRM of een persoon bekend is en of die gekoppeld is aan een bedrijf (company).

**XML Root:** `<PersonLookupRequest>`

**Verplichte velden:**
- `requestId` — UUID v4 of andere unieke identifier (voor correlatie met C10b response)
- `email` — RFC 5322 format

**Voorbeeld:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<PersonLookupRequest>
  <requestId>550e8400-e29b-41d4-a716-446655440000</requestId>
  <email>john.doe@example.com</email>
</PersonLookupRequest>
```

**Architecturale nota:**
- Lookup gebeurt in Release 1 op basis van e-mail
- Lookup op badgeCode kan later toegevoegd worden zodra badgeflow volledig vastligt
- Consumer moet `requestId` bewaren voor matching met response

---

### Contract C10b — Person Lookup Response (CRM → Kassa)

**Queue:** `crm.person.lookup.responded` | **Durable:** false  
**Relatie:** US-47

CRM antwoordt op een persoonscheck van Kassa.

**XML Root:** `<PersonLookupResponse>`

**Verplichte velden:**
- `requestId` — dezelfde UUID uit C10a (correlatie!)
- `found` — boolean (true/false)
- `linkedToCompany` — boolean (altijd false als found=false)

**Optioneel (alleen als found=true):**
- `id` — UUID v4 van de persoon in CRM
- `companyName` — naam van bedrijf
- `companyId` — UUID v4 van bedrijf (alleen als linkedToCompany=true)

**Voorbeeld (found=true, linked to company):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<PersonLookupResponse>
  <requestId>550e8400-e29b-41d4-a716-446655440000</requestId>
  <found>true</found>
  <linkedToCompany>true</linkedToCompany>
  <id>660e8400-e29b-41d4-a716-446655440001</id>
  <companyName>Acme Corp</companyName>
  <companyId>770e8400-e29b-41d4-a716-446655440002</companyId>
</PersonLookupResponse>
```

**Voorbeeld (found=false):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<PersonLookupResponse>
  <requestId>550e8400-e29b-41d4-a716-446655440000</requestId>
  <found>false</found>
  <linkedToCompany>false</linkedToCompany>
</PersonLookupResponse>
```

**Consumer-gedrag in Kassa:**
- Bij `found=true`: gebruiker lokaal koppelen aan order/payment-flow
- Bij `linkedToCompany=true`: company billing-logica activeren (facturatie)
- Bij `found=false`: fallback naar ter plaatse betalen of manuele afhandeling

---

### Contract C13 — User Confirmed (CRM → Kassa)

**Queue:** `crm.user.confirmed` | **Durable:** true  
**Relatie:** US-02, US-19

CRM publiceert een bevestigde gebruiker. Kassa consumeert dit als master data voor personen.

**XML Root:** `<UserConfirmed>`

**Verplichte velden:**
- `id` — UUID v4 (canonical ID vanuit CRM)
- `email` — RFC 5322
- `firstName` — string, max 80 chars
- `lastName` — string, max 80 chars
- `role` — enum: `VISITOR` | `COMPANY_CONTACT` | `SPEAKER` | `EVENT_MANAGER` | `CASHIER` | `BAR_STAFF` | `ADMIN`
- `isActive` — boolean
- `gdprConsent` — boolean (toestemming voor gegevensverwerking)
- `confirmedAt` — ISO 8601

**Optioneel:**
- `phone` — telefoonnummer
- `companyId` — UUID v4 (alleen als role=COMPANY_CONTACT)
- `badgeCode` — IoT badge-identificatie

**Voorbeeld:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<UserConfirmed>
  <id>880e8400-e29b-41d4-a716-446655440003</id>
  <email>alice@company.com</email>
  <firstName>Alice</firstName>
  <lastName>Smith</lastName>
  <phone>+32123456789</phone>
  <role>COMPANY_CONTACT</role>
  <companyId>770e8400-e29b-41d4-a716-446655440002</companyId>
  <badgeCode>BADGE-001</badgeCode>
  <isActive>true</isActive>
  <gdprConsent>true</gdprConsent>
  <confirmedAt>2026-05-01T10:00:00Z</confirmedAt>
</UserConfirmed>
```

**Architecturale nota:**
- De UUID van CRM is de canonical ID
- Kassa bewaart deze naast een eventuele native Odoo-ID
- Role bepaalt wat voor koppelingen (company, badges) mag plaatsvinden

---

### Contract C14 — Company Confirmed (CRM → Kassa)

**Queue:** `crm.company.confirmed` | **Durable:** true  
**Relatie:** US-40, US-20

CRM publiceert een bevestigd bedrijf. Kassa consumeert dit voor bedrijfskoppelingen en facturatieflows.

**XML Root:** `<CompanyConfirmed>`

**Verplichte velden:**
- `id` — UUID v4
- `vatNumber` — Belgisch BTW-nummer format `BE0123456789`
- `name` — bedrijfsnaam
- `email` — RFC 5322
- `isActive` — boolean
- `confirmedAt` — ISO 8601

**Voorbeeld:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<CompanyConfirmed>
  <id>770e8400-e29b-41d4-a716-446655440002</id>
  <vatNumber>BE0123456789</vatNumber>
  <name>Acme Corp</name>
  <email>info@acme.com</email>
  <isActive>true</isActive>
  <confirmedAt>2026-04-15T08:30:00Z</confirmedAt>
</CompanyConfirmed>
```

**Consumer-gedrag in Kassa:**
- Lokale referentie aanmaken of updaten
- Later kunnen koppelen aan gebruikers of transacties

---

### Contract C16 — Payment Confirmed (Kassa → CRM)

**Queue:** `kassa.payment.confirmed` | **Durable:** true  
**Relatie:** US-08, US-21

Kassa meldt een succesvolle betaling aan CRM. CRM werkt hiermee de betalingsstatus bij op het Contact.

**XML Root:** `<PaymentConfirmed>`

**Verplichte velden:**
- `email` — RFC 5322
- `amount` — decimal >= 0 (bijv. `50.00`)
- `currency` — `EUR`
- `paidAt` — ISO 8601

**Optioneel:**
- `userId` — UUID v4 (CRM user ID)
- `registrationId` — string (aanbevolen bij meerdere sessies per persoon)

**Voorbeeld:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<PaymentConfirmed>
  <userId>880e8400-e29b-41d4-a716-446655440003</userId>
  <email>alice@company.com</email>
  <registrationId>REG-2026-05-001</registrationId>
  <amount>50.00</amount>
  <currency>EUR</currency>
  <paidAt>2026-05-13T14:45:30Z</paidAt>
</PaymentConfirmed>
```

**Idempotentie:**
- Aanbevolen deduplicatie op: `email + paidAt + amount`
- Of: unieke `paymentReference` (indien later toegevoegd)
- CRM moet dubbele betalingen genegeerd via "already paid" check

---

### Contract C17a — Unpaid Request (Kassa → CRM)

**Queue:** `kassa.unpaid.requested` | **Durable:** true  
**Relatie:** US-07

Kassa vraagt aan CRM de lijst op van personen die nog niet betaald hebben.

**XML Root:** `<UnpaidRequest>`

**Verplichte velden:**
- `requestId` — UUID v4 (voor correlatie met C17b response)

**Voorbeeld:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<UnpaidRequest>
  <requestId>990e8400-e29b-41d4-a716-446655440004</requestId>
</UnpaidRequest>
```

---

### Contract C17b — Unpaid Response (CRM → Kassa)

**Queue:** `crm.unpaid.responded` | **Durable:** false  
**Relatie:** US-07

CRM antwoordt met de lijst van niet-betaalde personen.

**XML Root:** `<UnpaidResponse>`

**Verplichte velden:**
- `requestId` — dezelfde UUID uit C17a
- `persons` — array van personen

**Per persoon verplicht:**
- `id` — UUID v4
- `firstName` — string
- `lastName` — string
- `email` — RFC 5322
- `linkedToCompany` — boolean

**Per persoon optioneel:**
- `companyName` — string (alleen als linkedToCompany=true)

**Voorbeeld:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<UnpaidResponse>
  <requestId>990e8400-e29b-41d4-a716-446655440004</requestId>
  <persons>
    <person>
      <id>aa0e8400-e29b-41d4-a716-446655440005</id>
      <firstName>Bob</firstName>
      <lastName>Johnson</lastName>
      <email>bob@example.com</email>
      <linkedToCompany>false</linkedToCompany>
    </person>
    <person>
      <id>bb0e8400-e29b-41d4-a716-446655440006</id>
      <firstName>Carol</firstName>
      <lastName>Williams</lastName>
      <email>carol@companyB.com</email>
      <linkedToCompany>true</linkedToCompany>
      <companyName>Company B Inc</companyName>
    </person>
  </persons>
</UnpaidResponse>
```

**Consumer-gedrag in Kassa:**
- Tonen in on-site betalings-flow
- Gebruiken voor registratie- of check-in betalingen
- Lokaal niet hard cachen zonder update/deactivatie-logica

---

### Contract K-01 — Invoice Requested (Kassa → Facturatie)

**Queue:** `kassa.invoice.requested` | **Durable:** true  
**Relatie:** US (nog te koppelen door PMs)

Kassa stuurt een factuurverzoek naar Facturatie wanneer een bestelling/consumptie gekoppeld is aan een bedrijf en niet ter plaatse wordt afgerekend.

**XML Root:** `<InvoiceRequested>`

**Verplichte velden:**
- `orderId` — string (unieke order-ID in Kassa)
- `userId` — UUID v4 (persoon uit CRM)
- `companyId` — UUID v4 (bedrijf uit CRM)
- `amount` — decimal >= 0
- `currency` — `EUR`
- `orderedAt` — ISO 8601

**Verplicht in items array:**
- Per item:
  - `productName` — string
  - `quantity` — positief integer
  - `unitPrice` — decimal >= 0

**Optioneel:**
- `email` — RFC 5322
- `companyName` — string
- `eventId` — string
- `paymentReference` — string

**Voorbeeld:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<InvoiceRequested>
  <orderId>ORD-2026-05-00123</orderId>
  <userId>880e8400-e29b-41d4-a716-446655440003</userId>
  <companyId>770e8400-e29b-41d4-a716-446655440002</companyId>
  <amount>250.00</amount>
  <currency>EUR</currency>
  <orderedAt>2026-05-13T15:00:00Z</orderedAt>
  <items>
    <item>
      <productName>Conference Ticket</productName>
      <quantity>2</quantity>
      <unitPrice>100.00</unitPrice>
    </item>
    <item>
      <productName>Catering Package</productName>
      <quantity>1</quantity>
      <unitPrice>50.00</unitPrice>
    </item>
  </items>
  <email>billing@acme.com</email>
  <companyName>Acme Corp</companyName>
  <eventId>EVENT-2026-SPRING</eventId>
  <paymentReference>PAY-REF-001</paymentReference>
</InvoiceRequested>
```

**Idempotentie:**
- `orderId` is deduplicatiesleutel
- Facturatie moet duplo-orders genegeerd

**Businessregel:**
- Privépersonen gaan NIET via dit contract naar Facturatie
- Zij betalen ter plaatse, tenzij latere PM-beslissing uitzonderingsflow toevoegt

**Open PM-beslissing:**
- Moet Facturatie 1 bericht per order ontvangen?
- Of mag dit later gebatcht worden per gebruiker / per bedrijf / per event?

---

## Release 2 — User & Company Updates

### Contract C18 — User Updated (CRM → Kassa)

**Queue:** `crm.user.updated` | **Durable:** true  
**Relatie:** US-21, US-41

CRM publiceert een volledige update van een gebruiker. Kassa vervangt de lokale kopie volledig (geen partial merge).

**XML Root:** `<UserUpdated>`

**Verplichte velden:**
- `id` — UUID v4
- `email` — RFC 5322
- `firstName` — string
- `lastName` — string
- `role` — enum (zie C13)
- `isActive` — boolean
- `gdprConsent` — boolean
- `updatedAt` — ISO 8601

**Optioneel:**
- `phone`
- `companyId` — UUID v4
- `badgeCode`
- `street`
- `houseNumber`
- `postalCode`
- `city`
- `country` — ISO 3166-1 alpha-2 (bijv. `BE`, `NL`)

**Voorbeeld:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<UserUpdated>
  <id>880e8400-e29b-41d4-a716-446655440003</id>
  <email>alice.smith@company.com</email>
  <firstName>Alice</firstName>
  <lastName>Smith</lastName>
  <phone>+32987654321</phone>
  <role>COMPANY_CONTACT</role>
  <companyId>770e8400-e29b-41d4-a716-446655440002</companyId>
  <badgeCode>BADGE-001-NEW</badgeCode>
  <street>Rue de la Paix</street>
  <houseNumber>42</houseNumber>
  <postalCode>1000</postalCode>
  <city>Brussels</city>
  <country>BE</country>
  <isActive>true</isActive>
  <gdprConsent>true</gdprConsent>
  <updatedAt>2026-05-13T16:00:00Z</updatedAt>
</UserUpdated>
```

**Consumer-gedrag in Kassa:**
- Volledige replace van de lokale kopie
- Geen partial merge

---

### Contract C19 — Company Updated (CRM → Kassa)

**Queue:** `crm.company.updated` | **Durable:** true  
**Relatie:** US-41

CRM publiceert een volledige update van een bedrijf. Kassa vervangt de lokale kopie volledig.

**XML Root:** `<CompanyUpdated>`

**Verplichte velden:**
- `id` — UUID v4
- `vatNumber` — Belgisch BTW-nummer
- `name` — bedrijfsnaam
- `isActive` — boolean
- `updatedAt` — ISO 8601

**Optioneel:**
- `email`
- `phone`
- `street`
- `houseNumber`
- `postalCode`
- `city`
- `country` — ISO 3166-1 alpha-2

**Voorbeeld:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<CompanyUpdated>
  <id>770e8400-e29b-41d4-a716-446655440002</id>
  <vatNumber>BE0123456789</vatNumber>
  <name>Acme Corp International</name>
  <email>info@acme-intl.com</email>
  <phone>+32101010101</phone>
  <street>Boulevard Industriel</street>
  <houseNumber>100</houseNumber>
  <postalCode>2140</postalCode>
  <city>Antwerp</city>
  <country>BE</country>
  <isActive>true</isActive>
  <updatedAt>2026-05-12T09:15:00Z</updatedAt>
</CompanyUpdated>
```

**Consumer-gedrag in Kassa:**
- Volledige replace van de lokale kopie
- Geen partial merge

---

## Release 3 — GDPR & Deactivatie

### Contract C22 — User Deactivated (CRM → Kassa)

**Queue:** `crm.user.deactivated` | **Durable:** true  
**Relatie:** US-55

CRM meldt dat een gebruiker gedeactiveerd is. Dit is een soft delete-flow, nooit fysiek verwijderen.

**XML Root:** `<UserDeactivated>`

**Verplichte velden:**
- `id` — UUID v4
- `email` — RFC 5322
- `deactivatedAt` — ISO 8601

**Voorbeeld:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<UserDeactivated>
  <id>880e8400-e29b-41d4-a716-446655440003</id>
  <email>alice@company.com</email>
  <deactivatedAt>2026-05-13T17:00:00Z</deactivatedAt>
</UserDeactivated>
```

**Consumer-gedrag in Kassa:**
- Gebruiker verwijderen uit niet-betaalden lijst
- Geen nieuwe koppelingen meer maken aan nieuwe orders
- Bestaande audit trail behouden (geen fysieke delete)

---

### Contract C23 — Company Deactivated (CRM → Kassa)

**Queue:** `crm.company.deactivated` | **Durable:** true  
**Relatie:** US-54

CRM meldt dat een bedrijf gedeactiveerd is.

**XML Root:** `<CompanyDeactivated>`

**Verplichte velden:**
- `id` — UUID v4
- `vatNumber` — Belgisch BTW-nummer
- `deactivatedAt` — ISO 8601

**Voorbeeld:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<CompanyDeactivated>
  <id>770e8400-e29b-41d4-a716-446655440002</id>
  <vatNumber>BE0123456789</vatNumber>
  <deactivatedAt>2026-05-10T14:30:00Z</deactivatedAt>
</CompanyDeactivated>
```

**Consumer-gedrag in Kassa:**
- Geen nieuwe transacties of bestellingen meer koppelen aan dit bedrijf
- Bestaande historische transacties behouden
- Geen nieuwe factuurverzoeken via `kassa.invoice.requested`

---

## Algemene Richtlijnen

### XML Conventies
- **Root elements:** PascalCase (bijv. `<PaymentConfirmed>`)
- **Child velden:** camelCase (bijv. `<firstName>`, `<requestId>`)
- **Encoding:** UTF-8
- **Namespace:** Geen (geen `xmlns` declaratie)

### Request/Response Coupling
Wanneer je een `requestId` genereert:
1. Genereer unieke ID (UUID v4)
2. Bewaar `requestId` → originele request in memory/cache
3. Bij response: match `requestId` tegen cache

**Voorbeelden:**
- C10a → C10b (PersonLookupRequest/Response)
- C17a → C17b (UnpaidRequest/Response)

### Duplicate Handling
**Durable queues** voorkomen dataverlies, maar introduceren potentieel duplicaten:

- **C16 (PaymentConfirmed):** Deduplicatie op `email + paidAt + amount` of paymentReference
- **K-01 (InvoiceRequested):** Deduplicatie op `orderId`
- **C17b (UnpaidResponse):** Non-durable, geen deduplicatie nodig

### Optional Fields
Fields met geen vermelding van "Verplicht" zijn **optioneel**. Controleer altijd:

```python
if 'companyId' in user_confirmed:
    company_id = user_confirmed['companyId']
else:
    # Geen bedrijf
    pass
```

### Date/Time Format
Alle timestamps gebruiken **ISO 8601** format:
- `2026-05-13T14:30:45Z` (UTC, met Z suffix)
- `2026-05-13T14:30:45+02:00` (met timezone offset)

Aanbeveling: gebruik altijd UTC (Z suffix).

### Amounts & Currency
- **Amounts:** Decimal met 2 decimalen (bijv. `50.00`, `0.01`)
- **Currency:** Altijd `EUR` in deze fase

---

## Prioriteit per Use Case

### Essentiële Flows (Release 1)

**Check-in / Betaling ter plaatse:**
1. Ontvang C13 (user data) en C14 (company data) als voorbereiding
2. Bij betaling: verzend C16 (PaymentConfirmed)

**Company Transactions (Facturatie):**
1. Ontvang C13 + C14 + C18/C19 (updates)
2. Bij order: verzend K-01 (InvoiceRequested)

**Monitoring:**
- Continu C7 (heartbeat)
- Periodiek C8 (status check)
- Consumeer C9 (warnings) met grace-handling

### Lookup Flows
- Voor unknown personen: C10a (request) → C10b (response)
- Voor niet-betaalden: C17a (request) → C17b (response)

---

## Open Beslissingen & Nog af te Stemmen

1. **K-01 Batching:** Moet Facturatie berichten per order ontvangen of kunnen deze later gebatcht worden?
2. **C9 Severity:** Welke soort warnings triggeren wat in Kassa? (log only, notify, retry?)
3. **Retention Policy:** Hoe lang bewaart Kassa lokale kopies van C13/C14/C18/C19?
4. **Rate Limiting:** Limiet op C10a/C17a requests per minuut?
5. **Timezone Handling:** Hoe omgaan met timezones in orderedAt vs paidAt?

---

## Gerelateerde Documentatie

- [XSD_SCHEMA_DOCUMENTATIE_NL.md](XSD_SCHEMA_DOCUMENTATIE_NL.md) — XSD definities en validatie
- [DOCKER_KASSA_TEAM_NL.md](DOCKER_KASSA_TEAM_NL.md) — Container & deployment
- [CRM_USER_CREATION_INTEGRATION_NL.md](CRM_USER_CREATION_INTEGRATION_NL.md) — CRM integratie details
- [FACTURATIE_XML_BERICHTEN_NL.md](FACTURATIE_XML_BERICHTEN_NL.md) — Facturatie berichten

---

**Versie History:**
- **1.0** (Mei 2026) — Initial release, R1–R3 complete

**Contactpersoon:** Team Kassa
