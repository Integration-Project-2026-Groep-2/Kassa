Kassa POS — Top Up & VSC endpoint wijzigingen

Samenvatting
- Endpoint `/kassa_pos/get_vsc_code` is gestandaardiseerd om JSON responses te retourneren met een `ok`-veld: succes -> `{'ok': True, 'vsc_code': '...'}`; fout -> `{'ok': False, 'error': '...'}.`
- `export_for_printing` heeft nu een kleine aanpassing: betaalregels die betrekking hebben op Top Up krijgen het bedrag in de naam opgenomen, bijvoorbeeld `Top Up (gebruik €5.00)` zodat bonnen en exports duidelijkere labels tonen.

Details
1) `/kassa_pos/get_vsc_code`
- Locatie: `kassa_pos/controllers/pos_order_controller.py`
- Authenticatie: `auth='user'` (aanbevolen: veilige oproepen vanaf ingelogde POS clients). Als je externe apparaten wilt ondersteunen zonder Odoo-sessie, overweeg `auth='public'` + tokenvalidatie.
- Voorbeeld success-response:
  ```json
  {"ok": true, "vsc_code": "ABC123..."}
  ```
- Voorbeeld fout-response:
  ```json
  {"ok": false, "error": "order_not_found"}
  ```

2) `export_for_printing` wijziging
- Locatie: `kassa_pos/models/pos_order.py`
- Wat er is aangepast: betalingsregels in de teruggegeven `paymentlines` worden gecontroleerd op 'top up' (case-insensitive). Als gematcht, wordt de `name` aangevuld met het gebruikte bedrag, bv. `Top Up (gebruik €2.50)`.
- Effect: POS-receipts en export payloads tonen nu expliciet welk deel van de betaling van het Top Up-saldo kwam.

3) Test- & deploy-stappen
- Herstart Odoo zodat nieuwe controller-code actief is:
  ```powershell
  docker restart kassa-odoo-1
  Start-Sleep -Seconds 25
  ```
- Hard-refresh de POS-client (Ctrl+F5) en voer een testorder uit met:
  - Een Top Up betaling (controleer de `NumberPopup` flow en dat de betaalregel niet 0.00 is)
  - Print/preview de bon en controleer of de betaalregel `Top Up (gebruik €X.XX)` bevat
  - Controleer in de browser console of de RPC-call naar `/kassa_pos/get_vsc_code` `ok: true` teruggeeft (geen 404/401)

4) Security/aanbevelingen
- Laat de endpoint op `auth='user'` staan tenzij er een duidelijke reden is om publieke toegang te geven.
- Als je `auth='public'` wilt gebruiken, valideer een extra API-token of beperk oproepen per IP/whitelist.

5) Wanneer aanpassen
- Pas de response payload aan als de frontend meer informatie nodig heeft (bijv. `order_id` echoed, of extra VAT-breakdown). Hou altijd `ok` en `error` voor compatibiliteit.

Contact
- Als je wilt dat ik ook de frontend-update (bijv. ontvangst-template of gks_receipt.js) aanpas naar het nieuwe `{'ok': True, ...}` format, zeg het kort en ik implementeer het en test het in de POS-client.
