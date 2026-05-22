# XSD Schema Documentatie
## Kassa Integration Project
Integration Project 2025/2026 | Groep 2  
Auteur: Team Kassa | Versie: 1.1 | Maart 2026

---

## Inleiding

De Kassa-integratie maakt gebruik van drie XSD (XML Schema Definition) bestanden voor runtime-validatie van berichten op RabbitMQ. Deze schemas definiëren de contracten tussen Kassa en andere systemen (CRM, Facturatie, Controlroom).

**Validatie wordt uitgevoerd door:** `src/xml_validator.py` via de `lxml` library.

---

## 1. Schema-overzicht

| Bestand | Doel | Contracts | Release |
|---|---|---|---|
| `src/schema/kassa-schema-v1.xsd` | Master schema — CRM, Controlroom & Facturatie contracts | C7–C23, K-01 | R1–R3 |
| `src/schema/kassa_batch_contract.xsd` | Dagafsluitbatch schema | K-02 | R2 |
| `src/schema/contracts/kassa-user.xsd` | User CRUD schema — Kassa producer events | C36–C38 | R3 |

---

## 2. Master Schema: `kassa-schema-v1.xsd`

### Overzicht
Het master schema bevat alle berichten die Kassa ontvangt **en** verzendt (behalve user CRUD).

**Geen `targetNamespace`** — XML-berichten op de queue bevatten geen namespace-declaraties.

### Gedeelde Simple Types

#### Basis-types
```xml
<xs:simpleType name="UUIDType">
  <xs:restriction base="xs:string">
    <xs:pattern value="[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"/>
  </xs:restriction>
</xs:simpleType>

<xs:simpleType name="ISO8601DateTimeType">
  <xs:restriction base="xs:dateTime"/>
</xs:simpleType>

<xs:simpleType name="EmailType">
  <xs:restriction base="xs:string">
    <xs:pattern value="[^@\s]+@[^@\s]+\.[^@\s]+"/>
    <xs:maxLength value="254"/>
  </xs:restriction>
</xs:simpleType>
```

#### Country & VAT
```xml
<xs:simpleType name="CountryCodeType">
  <xs:restriction base="xs:string">
    <xs:pattern value="[A-Z]{2}"/>  <!-- ISO 3166-1 alpha-2 -->
  </xs:restriction>
</xs:simpleType>

<xs:simpleType name="BelgianVatNumberType">
  <xs:restriction base="xs:string">
    <xs:pattern value="BE[0-9]{10}"/>
  </xs:restriction>
</xs:simpleType>
```

#### Enums
```xml
<xs:simpleType name="UserRoleType">
  <xs:enumeration value="VISITOR"/>
  <xs:enumeration value="COMPANY_CONTACT"/>
  <xs:enumeration value="SPEAKER"/>
  <xs:enumeration value="EVENT_MANAGER"/>
  <xs:enumeration value="CASHIER"/>
  <xs:enumeration value="BAR_STAFF"/>
  <xs:enumeration value="ADMIN"/>
</xs:simpleType>

<xs:simpleType name="SystemStatusType">
  <xs:enumeration value="healthy"/>
  <xs:enumeration value="degraded"/>
  <xs:enumeration value="unhealthy"/>
  <xs:enumeration value="unknown"/>
</xs:simpleType>
```

### Contracten per Release

#### Release 1 (R1)

| Contract | Naar/Van | Richting | Queue | Durable |
|---|---|---|---|---|
| **C7** | Kassa → Controlroom | Publish | `kassa.heartbeat` | false |
| **C8** | Kassa → Controlroom | Publish | `kassa.status.checked` | false |
| **C9** | Controlroom → Kassa | Subscribe | `controlroom.warning.issued` | false |
| **C10a** | Kassa → CRM | Publish | `kassa.person.lookup.requested` | true |
| **C10b** | CRM → Kassa | Subscribe | `crm.person.lookup.responded` | false |
| **C13** | CRM → Kassa | Subscribe | `crm.user.confirmed` | true |
| **C14** | CRM → Kassa | Subscribe | `crm.company.confirmed` | true |
| **C16** | Kassa → CRM | Publish | `kassa.payment.confirmed` | true |
| **C17a** | Kassa → CRM | Publish | `kassa.unpaid.requested` | true |
| **C17b** | CRM → Kassa | Subscribe | `crm.unpaid.responded` | false |
| **K-01** | Kassa → Facturatie | Publish | `kassa.invoice.requested` | true |

#### Release 2 (R2)
Voegt contract C18 en C19 toe (user/company updates).

#### Release 3 (R3)
Voegt contract C22 en C23 toe (GDPR deactivatie).

### Belangrijke Contracten

#### Contract C7 — Heartbeat
```xml
<xs:element name="Heartbeat">
  <xs:complexType>
    <xs:sequence>
      <xs:element name="serviceId" type="ServiceIdKassaType"/>  <!-- altijd: KASSA -->
      <xs:element name="timestamp" type="ISO8601DateTimeType"/>
    </xs:sequence>
  </xs:complexType>
</xs:element>
```

**Frequentie:** Elke seconde  
**Queue:** `kassa.heartbeat` (non-durable)  
**Doel:** Controlroom weet dat Kassa nog draait

#### Contract C10a/10b — Personen Lookup (request/response)
```xml
<xs:element name="PersonLookupRequest">
  <xs:complexType>
    <xs:sequence>
      <xs:element name="requestId" type="xs:string"/>      <!-- koppeling request→response -->
      <xs:element name="email" type="EmailType"/>
    </xs:sequence>
  </xs:complexType>
</xs:element>

<xs:element name="PersonLookupResponse">
  <xs:complexType>
    <xs:sequence>
      <xs:element name="requestId" type="xs:string"/>      <!-- terugkoppeling -->
      <xs:element name="found" type="xs:boolean"/>
      <xs:element name="linkedToCompany" type="xs:boolean"/>
      <xs:element name="id" type="UUIDType" minOccurs="0"/>        <!-- alleen als found=true -->
      <xs:element name="companyName" type="xs:string" minOccurs="0"/>
      <xs:element name="companyId" type="UUIDType" minOccurs="0"/>
    </xs:sequence>
  </xs:complexType>
</xs:element>
```

**Application-level regel:** Response moet dezelfde `requestId` bevatten als de request zodat Kassa de koppeling kan maken.

#### Contract C13 — User Confirmed
```xml
<xs:element name="UserConfirmed">
  <xs:complexType>
    <xs:sequence>
      <xs:element name="id" type="UUIDType"/>
      <xs:element name="email" type="EmailType"/>
      <xs:element name="firstName" type="NameType"/>
      <xs:element name="lastName" type="NameType"/>
      <xs:element name="phone" type="xs:string" minOccurs="0"/>
      <xs:element name="role" type="UserRoleType"/>
      <xs:element name="companyId" type="UUIDType" minOccurs="0"/>  <!-- alleen role=COMPANY_CONTACT -->
      <xs:element name="badgeCode" type="xs:string" minOccurs="0"/>
      <xs:element name="isActive" type="xs:boolean"/>
      <xs:element name="gdprConsent" type="xs:boolean"/>
      <xs:element name="confirmedAt" type="ISO8601DateTimeType"/>
    </xs:sequence>
  </xs:complexType>
</xs:element>
```

**Application-level regel:** `companyId` alleen gebruiken als `role=COMPANY_CONTACT`. Andere rollen hebben geen bedrijfslink.

#### Contract K-01 — Invoice Request
```xml
<xs:element name="InvoiceRequested">
  <xs:complexType>
    <xs:sequence>
      <xs:element name="orderId" type="xs:string"/>
      <xs:element name="userId" type="UUIDType"/>
      <xs:element name="companyId" type="UUIDType"/>
      <xs:element name="amount" type="NonNegativeAmountType"/>
      <xs:element name="currency" type="CurrencyType"/>  <!-- EUR -->
      <xs:element name="orderedAt" type="ISO8601DateTimeTime"/>
      <xs:element name="items">
        <xs:complexType>
          <xs:sequence>
            <xs:element name="item" type="OrderItemType" minOccurs="1" maxOccurs="unbounded"/>
          </xs:sequence>
        </xs:complexType>
      </xs:element>
      <xs:element name="email" type="EmailType" minOccurs="0"/>
      <xs:element name="companyName" type="xs:string" minOccurs="0"/>
      <xs:element name="eventId" type="xs:string" minOccurs="0"/>
      <xs:element name="paymentReference" type="xs:string" minOccurs="0"/>
    </xs:sequence>
  </xs:complexType>
</xs:element>
```

**Doel:** Facturatie genereert factuur voor bedrijfstransacties (role=COMPANY_CONTACT)

---

## 3. Batch Schema: `kassa_batch_contract.xsd`

### Overzicht
Dit schema valideert het **BatchClosed** bericht dat Kassa stuurt bij dagafsluiting.

**Exchange:** `kassa.topic`  
**Routing key:** `kassa.closed`  
**Consumer-side queue:** `facturatie.kassa.batch.closed`  
**Durable:** true (met deduplicatie op `batchId`)

### Contract K-02 — Batch Closed
```xml
<xs:element name="BatchClosed">
  <xs:complexType>
    <xs:sequence>
      <xs:element name="batchId" type="UUIDType"/>
      <xs:element name="closedAt" type="ISO8601DateTimeType"/>
      <xs:element name="currency" type="CurrencyType"/>  <!-- EUR -->

      <!-- Gegroepeerde orders per CRM-gebruiker (optioneel bij lege batch) -->
      <xs:element name="users" minOccurs="0">
        <xs:complexType>
          <xs:sequence>
            <xs:element name="user" minOccurs="0" maxOccurs="unbounded">
              <xs:complexType>
                <xs:sequence>
                  <xs:element name="userId" type="UUIDType"/>  <!-- CRM user UUID -->
                  <xs:element name="items">
                    <xs:complexType>
                      <xs:sequence>
                        <xs:element name="item" type="BatchItemType" minOccurs="1" maxOccurs="unbounded"/>
                      </xs:sequence>
                    </xs:complexType>
                  </xs:element>
                  <xs:element name="totalAmount" type="NonNegativeAmountType"/>
                </xs:sequence>
              </xs:complexType>
            </xs:element>
          </xs:sequence>
        </xs:complexType>
      </xs:element>
    </xs:sequence>
  </xs:complexType>
</xs:element>
```

### BatchItemType
```xml
<xs:complexType name="BatchItemType">
  <xs:sequence>
    <xs:element name="productName" type="xs:string"/>
    <xs:element name="quantity" type="xs:positiveInteger"/>
    <xs:element name="unitPrice" type="NonNegativeAmountType"/>
    <xs:element name="totalPrice" type="NonNegativeAmountType"/>  <!-- berekend: quantity × unitPrice -->
  </xs:sequence>
</xs:complexType>
```

### Businessregels
- Alleen orders met `paymentType=Invoice` en geïdentificeerde klant zitten in batch
- `users` is optioneel: lege batch (geen invoice-orders) is geldig
- `summary` is altijd aanwezig (total amount)
- **Deduplicatie:** Gebruik `batchId` als sleutel; duplo's worden genegeerd

---

## 4. User CRUD Schema: `contracts/kassa-user.xsd`

### Overzicht
Dit **standalone** schema bevat user lifecycle events die Kassa **produceert** (niet consuminieert).

**NIET opgenomen via `xs:include` in master schema** — conflicten met Contract C22.

**Versie:** 1.10.1 (April 2026)

### Contracten

#### Contract C36 — User Created
```xml
<xs:element name="KassaUserCreated">
  <xs:complexType>
    <xs:sequence>
      <xs:element name="userId" type="xs:positiveInteger"/>          <!-- Odoo user ID (int) -->
      <xs:element name="firstName" type="NonEmptyStringType"/>      <!-- minLength=1 -->
      <xs:element name="lastName" type="NonEmptyStringType"/>
      <xs:element name="email" type="EmailType"/>
      <xs:element name="companyId" type="UUIDType" minOccurs="0"/>  <!-- optional -->
      <xs:element name="badgeCode" type="NonEmptyStringType"/>      <!-- IoT badge (PR #121) -->
      <xs:element name="role" type="UserRoleType"/>
      <xs:element name="createdAt" type="ISO8601DateTimeType"/>
    </xs:sequence>
  </xs:complexType>
</xs:element>
```

**Queue:** `crm.kassa.user.created`  
**Exchange:** `user.topic`  
**Routing key:** `kassa.user.created`  
**Durable:** true

#### Contract C37 — User Updated
```xml
<xs:element name="KassaUserUpdated">
  <xs:complexType>
    <xs:sequence>
      <xs:element name="userId" type="UUIDType"/>                    <!-- Nu UUID (niet int) -->
      <xs:element name="firstName" type="NonEmptyStringType"/>
      <xs:element name="lastName" type="NonEmptyStringType"/>
      <xs:element name="email" type="EmailType"/>
      <xs:element name="companyId" type="UUIDType" minOccurs="0"/>
      <xs:element name="badgeCode" type="NonEmptyStringType"/>      <!-- Verplicht! -->
      <xs:element name="role" type="UserRoleType"/>
      <xs:element name="updatedAt" type="ISO8601DateTimeType"/>
    </xs:sequence>
  </xs:complexType>
</xs:element>
```

**Queue:** `crm.kassa.user.updated`  
**Durable:** true

#### Contract C38 — User Deactivated
```xml
<xs:element name="UserDeactivated">
  <xs:complexType>
    <xs:sequence>
      <xs:element name="userId" type="UUIDType"/>
      <xs:element name="deactivatedAt" type="ISO8601DateTimeType"/>
    </xs:sequence>
  </xs:complexType>
</xs:element>
```

**Queue:** `crm.kassa.user.deactivated`  
**Durable:** true  
**Doel:** GDPR-verwijdering

### NonEmptyStringType
```xml
<xs:simpleType name="NonEmptyStringType">
  <xs:restriction base="xs:string">
    <xs:minLength value="1"/>
  </xs:restriction>
</xs:simpleType>
```

**Waarom:** Voorkomt lege `<badgeCode/>` die een IoT-badge zou wissen (PR #121).

---

## 5. Validatie in de Code

### xml_validator.py
Zie [src/xml_validator.py](../src/xml_validator.py)

```python
from lxml import etree

class XMLValidator:
    def __init__(self, schema_path):
        schema_doc = etree.parse(schema_path)
        self.schema = etree.XMLSchema(schema_doc)

    def validate(self, xml_string):
        try:
            doc = etree.fromstring(xml_string.encode('utf-8'))
            if self.schema.validate(doc):
                return True, "Valid"
            else:
                return False, self.schema.error_log
        except Exception as e:
            return False, str(e)
```

### Gebruik in receiver.py / sender.py

```python
# Inbound validation
validator_master = XMLValidator('src/schema/kassa-schema-v1.xsd')
validator_batch = XMLValidator('src/schema/kassa_batch_contract.xsd')
validator_user = XMLValidator('src/schema/contracts/kassa-user.xsd')

# Bij ontvangst van een bericht
is_valid, errors = validator_master.validate(xml_body)
if not is_valid:
    logger.error(f"Invalid XML: {errors}")
    # Reject message (NACK)
```

---

## 6. Best Practices

### Request/Response Coupling
Wanneer je een `requestId` genereert, zorg dat je:
1. Een unieke ID genereert (UUID v4)
2. Dit ID bijhoudt in memory/cache
3. De response matcht aan het originele request via `requestId`

Voorbeeld:
```python
import uuid

request_id = str(uuid.uuid4())
# Verzend PersonLookupRequest met request_id
# Bewaar request_id → originele request in cache

# Later: ontvang PersonLookupResponse
# Match response['requestId'] tegen cache
```

### Duplicate Handling
**Durable queues** voorkomen dataverlies, maar betekenen potentieel duplicaten:

- **BatchClosed:** Gebruik `batchId` als deduplicatiesleutel
- **PaymentConfirmed:** Idempotente operatie (dubbele payment wordt genegeerd door "already paid" check)

### Optional Fields
Fields met `minOccurs="0"` zijn optioneel. Controleer altijd:

```python
if 'companyId' in user_confirmed:
    # Gebruiker is gekoppeld aan bedrijf
    company_id = user_confirmed['companyId']
else:
    # Geen bedrijf
    pass
```

### Schema Versioning
De XSD-versies zijn vastgesteld:
- **kassa-schema-v1.xsd:** v1.1 (R1–R3)
- **kassa_batch_contract.xsd:** v1.0
- **kassa-user.xsd:** v1.10.1 (April 2026)

Wijzigingen vereisen overleg met CRM, Facturatie en Controlroom teams.

---

## 7. Troubleshooting

### Validatiefout: "Element 'companyId': This element is not expected"
**Oorzaak:** Je hebt `companyId` meegegeven in een contract waar het niet mag.  
**Fix:** Controleer `minOccurs` en `maxOccurs` in schema.

### Validatiefout: "Value '...' is not valid with respect to pattern"
**Oorzaak:** Waarde voldoet niet aan regex-patroon (bijv. email, UUID).  
**Fix:** Controleer het invoerformat:
```python
# Email
import re
email_pattern = r"[^@\s]+@[^@\s]+\.[^@\s]+"
assert re.match(email_pattern, email)

# UUID v4
uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
assert re.match(uuid_pattern, user_id)
```

### Bericht wordt afgewezen door receiver
**Checklist:**
1. Is XML-syntax correct? (wellformed XML)
2. Valideert tegen correcte schema?
3. Zijn verplichte velden aanwezig?
4. Voldoen waarden aan patroonbeperkingen?

---

## 8. Gerelateerde Documentatie

- [DOCKER_KASSA_TEAM_NL.md](DOCKER_KASSA_TEAM_NL.md) — Container & deployment
- [CRM_USER_CREATION_INTEGRATION_NL.md](CRM_USER_CREATION_INTEGRATION_NL.md) — CRM integratie & user lifecycle
- [FACTURATIE_XML_BERICHTEN_NL.md](FACTURATIE_XML_BERICHTEN_NL.md) — Facturatie berichten en RabbitMQ topologie
- [KASSA_POS_TOPUP_AND_VSC_CHANGES.md](KASSA_POS_TOPUP_AND_VSC_CHANGES.md) — POS integratie details

---

**Vragen of aanpassingen?** Neem contact op met Team Kassa.
