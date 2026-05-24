# Kassa Contracts — RabbitMQ Integration Specification
## All RabbitMQ contracts maintained by Team Kassa
Integration Project 2025/2026 | Group 2
Author: Team Kassa | Version: 1.0 | May 2026

---

## Quick Reference — Contract overview

### Release 1 (R1)
| Contract | Direction | Queue | Durable | Essential? |
|---|---|---|---|---|
| **C7** | Kassa → Controlroom | `kassa.heartbeat` | false | ✅ |
| **C8** | Kassa → Controlroom | `kassa.status.checked` | false | ✅ |
| **C10a** | Kassa → CRM | `kassa.person.lookup.requested` | true | ✅ |
| **K-01** | Kassa → Invoicing | `kassa.invoice.requested` | true | ✅ |

---

## Release 1 — Core Contracts

### Contract C7 — Heartbeat (Kassa → Controlroom)

**Queue:** `kassa.heartbeat` | **Durable:** false  
**Frequency:** Every second

Kassa publishes a lightweight heartbeat so Controlroom can detect whether the Kassa service is running.

---

Refer to `src/schema/` for the canonical XSDs used by each contract. Also see `docs/XSD_SCHEMA_DOCUMENTATION.md` for a high-level schema overview.
