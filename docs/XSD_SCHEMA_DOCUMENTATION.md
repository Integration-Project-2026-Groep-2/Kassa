# XSD Schema Documentation
## Kassa Integration Project
Integration Project 2025/2026 | Group 2
Author: Team Kassa | Version: 1.1 | March 2026

---

## Introduction

The Kassa integration uses three XSD (XML Schema Definition) files for runtime validation of messages on RabbitMQ. These schemas define the contracts between Kassa and other systems (CRM, Invoicing, Controlroom).

**Validation is performed by:** `src/xml_validator.py` using the `lxml` library.

---

## 1. Schema overview

| File | Purpose | Contracts | Release |
|---|---|---|---|
| `src/schema/kassa-schema-v1.xsd` | Master schema — CRM, Controlroom & Invoicing contracts | C7–C23, K-01 | R1–R3 |
| `src/schema/kassa_batch_contract.xsd` | Daily batch schema | K-02 | R2 |
| `src/schema/contracts/kassa-user.xsd` | User CRUD schema — Kassa producer events | C36–C38 | R3 |

---

## 2. Master Schema: `kassa-schema-v1.xsd`

### Overview
The master schema contains all messages that Kassa receives **and** sends (except user CRUD).

**No `targetNamespace`** — XML messages on the queue contain no namespace declarations.

### Shared Simple Types

#### Base types
```xml
<xs:simpleType name="UUIDType"> ... </xs:simpleType>
```

#### Country & VAT
```xml
<xs:simpleType name="CountryCodeType"> ... </xs:simpleType>
```

#### Enums
```xml
<xs:simpleType name="UserRoleType"> ... </xs:simpleType>
```

### Contracts per Release

#### Release 1 (R1)

| Contract | From/To | Direction | Queue | Durable |
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
| **K-01** | Kassa → Invoicing | Publish | `kassa.invoice.requested` | true |

---

## 3. Batch Schema: `kassa_batch_contract.xsd`

### Overview
This schema validates the **BatchClosed** message Kassa sends at end-of-day.

**Exchange:** `kassa.topic`
**Routing key:** `kassa.closed`
**Consumer-side queue:** `facturatie.kassa.batch.closed`
**Durable:** true (with deduplication on `batchId`)

---

Refer to the original Dutch file for the full detailed XSD excerpts if needed; this document mirrors the schema content used by the code in `src/schema/`.
