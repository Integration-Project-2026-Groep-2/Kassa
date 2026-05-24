Kassa POS — Top Up & VSC endpoint changes

Summary
- The `/kassa_pos/get_vsc_code` endpoint now standardizes JSON responses with an `ok` field: success -> `{'ok': True, 'vsc_code': '...'}`; error -> `{'ok': False, 'error': '...'}`.
- `export_for_printing` includes a small change: payment lines related to Top Up include the used amount in the name, for example `Top Up (used €5.00)` so receipts and exports show clearer labels.

Details
1) `/kassa_pos/get_vsc_code`
- Location: `kassa_pos/controllers/pos_order_controller.py`
- Authentication: `auth='user'` (recommended for secure calls from logged-in POS clients). If you need to support external devices without an Odoo session, consider `auth='public'` + token validation.
- Example success response:
  ```json
  {"ok": true, "vsc_code": "ABC123..."}
  ```
- Example error response:
  ```json
  {"ok": false, "error": "order_not_found"}
  ```

2) `export_for_printing` change
- Location: `kassa_pos/models/pos_order.py`
- What changed: payment lines in the returned `paymentlines` are checked for 'top up' (case-insensitive). If matched, the `name` is appended with the used amount, e.g. `Top Up (used €2.50)`.
- Effect: POS receipts and export payloads now explicitly show which part of the payment came from the Top Up balance.

3) Test & deploy steps
- Restart Odoo so the new controller code is active:
  ```powershell
  docker restart kassa-odoo-1
  Start-Sleep -Seconds 25
  ```
- Hard-refresh the POS client (Ctrl+F5) and perform a test order with:
  - A Top Up payment (check the `NumberPopup` flow and that the payment line is not 0.00)
  - Print/preview the receipt and verify the payment line contains `Top Up (used €X.XX)`
  - Check the browser console that the RPC call to `/kassa_pos/get_vsc_code` returns `ok: true` (no 404/401)

4) Security / recommendations
- Keep the endpoint at `auth='user'` unless there is a clear reason to provide public access.
- If you choose `auth='public'`, validate an extra API token or restrict calls by IP/whitelist.

5) When to adapt
- Adjust the response payload if the frontend needs more information (e.g. echo `order_id`, or add extra VAT breakdown). Always keep `ok` and `error` for compatibility.

Contact
- If you want me to also update the frontend (e.g. receipt template or gks_receipt.js) to the new `{'ok': True, ...}` format, tell me and I will implement and test it in the POS client.
