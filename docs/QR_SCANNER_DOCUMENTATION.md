# QR Scanner — Kassa Documentation (v1.0)

## Purpose

This document describes how the QR scanner works in the Kassa POS system — how customers are linked to orders via their QR code, how the badge code lookup is implemented in code, and what still needs to be done to complete the RabbitMQ integration.

---

## Summary

The Kassa POS system includes a camera-based QR code scanner. When a customer shows their QR code (containing a `qr_token`), the cashier scans it and the customer is automatically linked to the current order.

Kassa only needs the `badge_code` field on the partner record to identify the correct customer. The `badge_code` is stored on the `res.partner` model in Odoo.

---

## What Kassa does

- Stores `badge_code` on the partner record in Odoo (via RabbitMQ receiver, once implemented)
- Scans QR codes at the POS terminal and links the matching customer to the active order

---

## How the qr_token reaches Kassa

The frontend team sends the `qr_token` via RabbitMQ to Kassa after a user registers. The receiver stores it as `badge_code` on the partner record in Odoo.

> **Current status (temporary — for testing):** The RabbitMQ integration for `qr_token` is not yet implemented. For testing purposes, `badge_code` is set manually on partner records in Odoo. This will be replaced once the receiver is extended.

---

## Scanner flow

```
Customer shows QR code on their phone at the POS terminal
    ↓
Cashier clicks the Scanner button → camera opens
    ↓
jsQR library decodes the QR code → extracts qr_token
    ↓
System searches partner by badge_code in the local POS cache
    ↓
Not found locally → RPC search in Odoo (badge_code OR user_id_custom)
    ↓
Found → automatically linked to the current order via set_partner()
    ↓
Not found → warning notification shown to the cashier
```

---

## How the scanner works

The cashier clicks the **Scanner** button on the product screen. The browser opens the camera and the customer holds up their QR code. The scanner uses the **jsQR** library (canvas-based) and works in Chrome, Firefox, and Edge.

### Scanner button

The button is registered on the `ProductScreen` via `addControlButton()`. It opens a dialog (`QrScannerDialog`) that starts the camera stream and continuously decodes frames using jsQR.

**File:** [`kassa_pos/static/src/js/QrScannerButton.js`](kassa_pos/static/src/js/QrScannerButton.js)

```js
ProductScreen.addControlButton({
    component: QrScannerButton,
    position: ["after", "ClosingButton"],
    condition: () => true,
});
```

---

## Badge code lookup logic

When a QR code is detected, `_findPartnerByBadgeCode(badgeCode)` is called.

### Step 1 — Local POS cache (fast)

```js
const partners = this.pos.db.get_partners_sorted();
const local = partners.find((p) => p.badge_code === badgeCode);
if (local) return local;
```

### Step 2 — RPC fallback to Odoo

If the partner is not found in the local cache, a server-side search is performed. The search uses an **OR condition** on both `badge_code` and `user_id_custom`:

```js
const result = await this.orm.searchRead(
    "res.partner",
    ["|", ["badge_code", "=", badgeCode], ["user_id_custom", "=", badgeCode]],
    ["id", "name", "email", "phone", "badge_code", "role", "company_id_custom", "user_id_custom"],
    { limit: 1 }
);
```

> Note: The RPC query matches on **either** `badge_code` **or** `user_id_custom`. This ensures compatibility during the transition period before full RabbitMQ integration is in place.

If found, the partner is added to the local cache and returned. If not found, a warning notification is shown and scanning resumes after 1.5 seconds.

---

## Linking the customer to the order

Once a partner is found, it is linked to the current active order:

```js
const currentOrder = this.pos.get_order();
if (currentOrder) {
    currentOrder.set_partner(partner);
}
```

A success notification is shown and the scanner dialog closes automatically after 900 ms.

---

## QR icon in partner views (temporary)

A QR code icon button ("Show QR Code") is displayed in the partner form view and kanban view. This button is visible only when the partner has a **`badge_code`** set.

**File:** [`kassa_pos/views/res_partner_views.xml`](kassa_pos/views/res_partner_views.xml)

```xml
<button name="action_generate_qrcode" type="object" string="Show QR Code"
    modifiers="{'invisible': [('badge_code', '=', False)]}"
    class="btn-primary" icon="fa-qrcode"/>
```

> This is a **temporary** feature for internal testing. Once the frontend is ready and QR codes are accessible via the user account, this icon will be removed.

---

## Partner model fields

Relevant fields added to `res.partner` for QR/scanner functionality:

| Field | Type | Description |
|---|---|---|
| `badge_code` | Char (indexed) | Badge or QR token — used to identify the customer at the POS |
| `user_id_custom` | Char (indexed) | UUID for user identification — also used as fallback in badge lookup |
| `role` | Selection | Customer, Cashier, Admin |
| `company_id_custom` | Char | Optional UUID for company linkage |

**File:** [`kassa_pos/models/res_partner.py`](kassa_pos/models/res_partner.py)

---

## What still needs to be done

| Task | Priority |
|---|---|
| Extend receiver to consume `qr_token` via RabbitMQ and store it as `badge_code` on the partner record | High |
| Remove QR icon from partner views once frontend is ready | Medium |
| Secure the API for production use | Medium |

---

## Code references

| File | Purpose |
|---|---|
| [`kassa_pos/static/src/js/QrScannerButton.js`](kassa_pos/static/src/js/QrScannerButton.js) | Scanner dialog, jsQR integration, badge code lookup, partner linking |
| [`kassa_pos/static/src/js/BadgeScanner.js`](kassa_pos/static/src/js/BadgeScanner.js) | Barcode scanner extension — detects badge codes from physical scanners |
| [`kassa_pos/static/src/css/qr_scanner.css`](kassa_pos/static/src/css/qr_scanner.css) | Scanner dialog styles (overlay, frame animation, success panel) |
| [`kassa_pos/static/src/lib/jsQR.min.js`](kassa_pos/static/src/lib/jsQR.min.js) | jsQR library — canvas-based QR decoding |
| [`kassa_pos/models/res_partner.py`](kassa_pos/models/res_partner.py) | Partner model with `badge_code` and `user_id_custom` fields |
| [`kassa_pos/views/res_partner_views.xml`](kassa_pos/views/res_partner_views.xml) | QR icon in partner form and kanban views |

---

## Version history

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-05-25 | Initial documentation — based on current implementation; corrects QR icon field (badge_code, not user_id_custom); documents dual-field RPC lookup |

---

## Contact & support

For integration questions or schema updates refer to:
- Architecture docs: `docs/ARCHITECTURE.md`
- RabbitMQ setup: `docs/RABBITMQ_SETUP.md`
- Deployment guide: `docs/AZURE_DEPLOYMENT_GUIDE.md`
