# Invoicing — XML Messages sent by Kassa (v1.9)

## Purpose

This document describes the XML messages Kassa publishes to the Invoicing system via RabbitMQ, the exchanges/queues used, and the payload structure.

## Summary

| Message | Purpose | RabbitMQ route | XML root |
|---|---|---|---|
| `PaymentConfirmed` | Confirm payment towards CRM | Default exchange `''` → queue `kassa.payment.confirmed` | `<PaymentConfirmed>` |
| `InvoiceRequested` | Invoice request for business order | Default exchange `''` → queue `kassa.invoice.requested` | `<InvoiceRequested>` |
| `BatchClosed` | End-of-day batch with invoice orders | Exchange `kassa.topic` → routing key `kassa.closed` | `<BatchClosed>` |

---

## 1. PaymentConfirmed

When a POS order is marked as paid, and an email address is present, Kassa attempts to send `PaymentConfirmed` to CRM.

### RabbitMQ route
- Exchange: default exchange `''`
- Routing key: `kassa.payment.confirmed`
- Queue: `kassa.payment.confirmed` (durable)

### XML structure (summary)
- `userId` (optional)
- `email` (required)
- `amount` (required)
- `currency` (required, `EUR`)
- `paidAt` (required, ISO 8601)

Refer to `src/messaging/message_builders.py` for the concrete builder and `kassa_pos/models/pos_order.py` for the trigger.
