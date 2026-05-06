# Saldo Systeem — Technische Documentatie

**Module:** `kassa_pos`  
**Versie:** 1.0  
**Datum:** 2026-05-06  
**Auteur:** Team Kassa

---

## Inhoudsopgave

1. [Overzicht](#1-overzicht)
2. [Architectuur](#2-architectuur)
3. [Database Modellen](#3-database-modellen)
4. [Backend Controllers](#4-backend-controllers)
5. [POS Frontend](#5-pos-frontend)
6. [Betaalvalidatie](#6-betaalvalidatie)
7. [Transactiegeschiedenis](#7-transactiegeschiedenis)
8. [Beveiliging & Toegangsrechten](#8-beveiliging--toegangsrechten)
9. [Gewijzigde Bestanden](#9-gewijzigde-bestanden)
10. [Testhandleiding](#10-testhandleiding)
11. [Businessregels](#11-businessregels)

---

## 1. Overzicht

Het Saldo Systeem voegt een digitale portemonnee toe aan het Odoo POS-systeem. Klanten kunnen saldo opladen via cash of bancontact, en dat saldo vervolgens gebruiken als betaalmethode aan de kassa.

### Kernfunctionaliteiten

| Functie | Beschrijving |
|---|---|
| Saldo opladen | Via POS-knop, min. €5, cash of kaart |
| Saldo betalen | "Saldo" als betaalmethode in het POS |
| Klant zoeken | Op naam, e-mailadres of badge code |
| Saldo controle | Blokkeert betaling bij onvoldoende saldo |
| Transactiegeschiedenis | Elke top-up en betaling bewaard in DB |
| Saldo ≥ 0 | Saldo kan nooit negatief worden |

---

## 2. Architectuur

```
┌─────────────────────────────────────────────────────┐
│                    POS Frontend (OWL)                │
│                                                     │
│  BalanceButton.js  →  BalanceTopupModal.js          │
│  (Control bar)        (Dialoogvenster: zoek + laad) │
│                                                     │
│  BalanceValidation.js                               │
│  (Patch op PaymentScreen: controle bij betaling)    │
└────────────────────────┬────────────────────────────┘
                         │ JSON-RPC over HTTP
┌────────────────────────▼────────────────────────────┐
│              Backend Controllers (Python)            │
│                                                     │
│  /kassa/balance/search   — klant opzoeken           │
│  /kassa/balance/topup    — saldo opladen            │
│  /kassa/balance/deduct   — saldo aftrekken          │
│  /kassa/balance/get      — saldo ophalen            │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│                  Odoo ORM / PostgreSQL               │
│                                                     │
│  res.partner           — balance (Float) veld       │
│  balance.transaction   — volledige transactie log   │
│  pos.order             — saldo verwerking bij close │
└─────────────────────────────────────────────────────┘
```

---

## 3. Database Modellen

### 3.1 `res.partner` — Saldo veld

**Bestand:** [kassa_pos/models/res_partner.py](../kassa_pos/models/res_partner.py)

Het bestaande `res.partner` model is uitgebreid met een `balance` veld:

```python
balance = fields.Float(
    string='Saldo (€)',
    default=0.0,
    digits=(10, 2),
    help='Huidig saldo van de klant in euro'
)
```

- Standaardwaarde: `0.0`
- Precisie: 2 decimalen
- Kan nooit negatief worden (gecontroleerd in controller en frontend)

### 3.2 `balance.transaction` — Transactiegeschiedenis

**Bestand:** [kassa_pos/models/balance_transaction.py](../kassa_pos/models/balance_transaction.py)

Nieuw model dat elke saldo-mutatie bijhoudt:

```python
class BalanceTransaction(models.Model):
    _name = 'balance.transaction'
    _description = 'Saldo Transactie'
    _order = 'create_date desc'

    partner_id      = Many2one('res.partner')     # Verplicht, cascade restrict
    amount          = Float(digits=(10,2))         # + = opladen, - = betaling
    transaction_type = Selection(['topup','payment'])
    payment_method  = Selection(['cash','card','balance'])
    note            = Char()
    pos_order_id    = Many2one('pos.order')        # Optioneel, set null bij verwijderen
    balance_after   = Float(digits=(10,2))         # Saldo ná de transactie
```

#### Veldwaarden per transactietype

| Type | `amount` | `transaction_type` | `payment_method` |
|---|---|---|---|
| Saldo opladen | `+5.00` | `topup` | `cash` of `card` |
| Betaling via saldo | `-12.50` | `payment` | `balance` |

---

## 4. Backend Controllers

**Bestand:** [kassa_pos/controllers/balance_controller.py](../kassa_pos/controllers/balance_controller.py)

Alle routes zijn JSON-RPC (`type='json'`), vereisen authenticatie (`auth='user'`), en accepteren alleen POST-verzoeken.

### 4.1 `GET /kassa/balance/search`

Zoekt klanten op naam, e-mail of badge code.

**Request:**
```json
{ "query": "jan" }
```

**Response (success):**
```json
[
  {
    "id": 42,
    "name": "Jan Peeters",
    "email": "jan@voorbeeld.be",
    "badge_code": "A1B2C3",
    "balance": 25.50
  }
]
```

- Enkel partners met `user_id_custom` ingesteld (= POS-gebruikers)
- Maximaal 10 resultaten
- Minimaal 1 karakter vereist

### 4.2 `POST /kassa/balance/topup`

Laadt saldo op voor een klant.

**Request:**
```json
{
  "partner_id": 42,
  "amount": 20.00,
  "payment_method": "cash"
}
```

**Response (success):**
```json
{
  "success": true,
  "new_balance": 45.50,
  "name": "Jan Peeters"
}
```

**Validaties:**
- `partner_id` moet bestaan
- `amount >= 5.0` (minimum €5)
- `payment_method` moet `cash` of `card` zijn (niet `balance`)

**Bij succes:**
1. `partner.balance += amount`
2. Nieuwe `balance.transaction` aangemaakt (type: `topup`)
3. Log in Odoo server logs

### 4.3 `POST /kassa/balance/deduct`

Trekt saldo af van een klant (wordt intern gebruikt bij orderverwerking).

**Request:**
```json
{
  "partner_id": 42,
  "amount": 12.50,
  "pos_order_id": 99
}
```

**Response (success):**
```json
{
  "success": true,
  "new_balance": 33.00
}
```

**Validaties:**
- `partner.balance >= amount`

### 4.4 `POST /kassa/balance/get`

Haalt het huidig saldo op van een klant.

**Request:**
```json
{ "partner_id": 42 }
```

**Response:**
```json
{
  "success": true,
  "balance": 33.00,
  "name": "Jan Peeters"
}
```

---

## 5. POS Frontend

### 5.1 BalanceButton.js

**Bestand:** [kassa_pos/static/src/js/BalanceButton.js](../kassa_pos/static/src/js/BalanceButton.js)

Een OWL-component dat een "Saldo" knop toevoegt aan de POS control bar (onderaan het productscherm).

```javascript
ProductScreen.addControlButton({
    component: BalanceButton,
    condition: function () { return true; },
});
```

- Altijd zichtbaar (ook voor kassierbeheerder)
- Opent bij klik: `BalanceTopupModal`
- Icoon: Font Awesome wallet (`fa-wallet`)

### 5.2 BalanceTopupModal.js

**Bestand:** [kassa_pos/static/src/js/BalanceTopupModal.js](../kassa_pos/static/src/js/BalanceTopupModal.js)

Tweedelig OWL-dialoogvenster voor het opladen van saldo.

#### Stap 1 — Klant zoeken

- Tekstveld met debounce (300ms) op `input` event
- Zoekt via `/kassa/balance/search`
- Toont lijst met naam, e-mail en huidig saldo
- Klik op een resultaat → naar Stap 2

#### Stap 2 — Bedrag en betaalmethode

- Geselecteerde klant met huidig saldo zichtbaar
- Bedragveld (min. 5, stap 0.01)
- Snelknoppen: €5 / €10 / €20 / €50
- Betaalmethode: Cash (standaard) of Kaart
- "Andere klant" knop → terug naar Stap 1

#### Bevestigen

- Clientvalidatie: amount ≥ 5
- RPC naar `/kassa/balance/topup`
- Succes → bevestigingsboodschap + modal sluit
- Fout → foutmelding inline in modal

### 5.3 State Management

```javascript
this.state = useState({
    query: '',
    results: [],
    searching: false,
    selectedPartner: null,
    amount: 0,
    paymentMethod: 'cash',
    loading: false,
    error: '',
    success: '',
});
```

---

## 6. Betaalvalidatie

**Bestand:** [kassa_pos/static/src/js/BalanceValidation.js](../kassa_pos/static/src/js/BalanceValidation.js)

Dit bestand patcht `PaymentScreen.prototype` via de officiële Odoo `patch()` utility. Twee methodes worden overschreven:

### 6.1 `selectPaymentMethod` — Bij toevoegen Saldo betaalmethode

Wanneer de kassier "Saldo" kiest als betaalmethode:

1. Controleer of er een klant geselecteerd is → anders: waarschuwing
2. Haal huidig saldo op via `/kassa/balance/get`
3. Als saldo = 0 → blokkeer met melding "Geen saldo beschikbaar"
4. Anders: voeg betaallijn toe en vul automatisch het maximale bedrag in:
   ```
   maxAmount = min(saldo, openstaand bedrag)
   ```
5. Toon informatiemelding: "Beschikbaar saldo: €X — Ingevuld: €Y"

### 6.2 `validateOrder` — Bij valideren van de betaling

Wanneer de kassier op "Bevestigen" drukt:

1. Controleer of er een Saldo-betaallijn aanwezig is
2. Zo ja: haal opnieuw het saldo op via `/kassa/balance/get`
3. Als `saldo < gevraagd bedrag` → blokkeer betaling met foutmelding
4. Zo niet: ga door naar `super.validateOrder()`

**Na validatie (backend — pos_order.py):**

Bij elke betaalde order roept `create_from_ui` automatisch `_process_balance_payment` aan:

```python
def _process_balance_payment(self, order):
    for payment in order.payment_ids:
        if 'saldo' in payment.payment_method_id.name.lower():
            new_balance = max(0.0, partner.balance - payment.amount)
            partner.write({'balance': new_balance})
            self.env['balance.transaction'].create({...})
```

---

## 7. Transactiegeschiedenis

Elke saldo-mutatie wordt bijgehouden in `balance.transaction`.

### Voorbeeld transacties in PostgreSQL

```sql
SELECT
    bt.id,
    rp.name AS klant,
    bt.amount,
    bt.transaction_type,
    bt.payment_method,
    bt.balance_after,
    bt.note,
    bt.create_date
FROM balance_transaction bt
JOIN res_partner rp ON rp.id = bt.partner_id
ORDER BY bt.create_date DESC;
```

### Voorbeeld output

| klant | amount | type | methode | saldo_na | notitie |
|---|---|---|---|---|---|
| Jan Peeters | -12.50 | payment | balance | 7.50 | Betaling via saldo — order POS/001 |
| Jan Peeters | +20.00 | topup | cash | 20.00 | Saldo opladen via POS (cash) |

### Inzien via Odoo UI

Ga naar: **Instellingen → Technisch → Saldo Transacties**  
(of direct via URL: `/odoo/balance-transaction`)

---

## 8. Beveiliging & Toegangsrechten

**Bestand:** [kassa_pos/security/ir.model.access.csv](../kassa_pos/security/ir.model.access.csv)

| Model | Groep | Lezen | Schrijven | Aanmaken | Verwijderen |
|---|---|---|---|---|---|
| `balance.transaction` | POS Gebruiker | ✓ | ✓ | ✓ | ✗ |
| `balance.transaction` | POS Beheerder | ✓ | ✓ | ✓ | ✓ |

- POS-gebruikers kunnen transacties aanmaken maar niet verwijderen (audit trail)
- Saldo-endpoints vereisen `auth='user'` (ingelogde Odoo sessie)

---

## 9. Gewijzigde Bestanden

### Nieuwe bestanden

| Bestand | Doel |
|---|---|
| [kassa_pos/models/balance_transaction.py](../kassa_pos/models/balance_transaction.py) | Transactie model |
| [kassa_pos/controllers/balance_controller.py](../kassa_pos/controllers/balance_controller.py) | HTTP endpoints |
| [kassa_pos/controllers/__init__.py](../kassa_pos/controllers/__init__.py) | Controllers package |
| [kassa_pos/static/src/js/BalanceButton.js](../kassa_pos/static/src/js/BalanceButton.js) | POS control bar knop |
| [kassa_pos/static/src/js/BalanceTopupModal.js](../kassa_pos/static/src/js/BalanceTopupModal.js) | Saldo opladen dialoog |
| [kassa_pos/static/src/js/BalanceValidation.js](../kassa_pos/static/src/js/BalanceValidation.js) | Betaalscherm validatie |

### Gewijzigde bestanden

| Bestand | Wijziging |
|---|---|
| [kassa_pos/models/res_partner.py](../kassa_pos/models/res_partner.py) | `balance` Float veld toegevoegd |
| [kassa_pos/models/__init__.py](../kassa_pos/models/__init__.py) | `balance_transaction` import |
| [kassa_pos/models/pos_order.py](../kassa_pos/models/pos_order.py) | `_process_balance_payment` + aanroep in `create_from_ui` |
| [kassa_pos/__init__.py](../kassa_pos/__init__.py) | `controllers` import |
| [kassa_pos/__manifest__.py](../kassa_pos/__manifest__.py) | 3 JS-bestanden toegevoegd aan assets |
| [kassa_pos/data/pos_config_data.xml](../kassa_pos/data/pos_config_data.xml) | `Saldo` betaalmethode aangemaakt |
| [kassa_pos/security/ir.model.access.csv](../kassa_pos/security/ir.model.access.csv) | Toegangsrechten voor `balance.transaction` |
| [kassa_pos/static/src/css/user_registration.css](../kassa_pos/static/src/css/user_registration.css) | Stijlen voor balance UI |

---

## 10. Testhandleiding

### Vereisten

- Odoo draait lokaal via Docker (`docker compose up -d`)
- Module geïnstalleerd: `kassa_pos`
- Admin ingelogd op `http://localhost:8069`

### Test 1 — Saldo Opladen

1. Open het POS: **Point of Sale → Kassa Main → Open**
2. Klik op de **"Saldo"** knop in de control bar (onderaan)
3. Typ de naam van een testklant (bijv. "Test")
4. Selecteer een klant uit de resultatenlijst
5. Kies een bedrag (bijv. €20)
6. Selecteer betaalmethode: **Cash**
7. Klik **"Saldo Opladen"**
8. Verwacht: bevestigingsboodschap met nieuw saldo

**Verificatie in DB:**
```sql
SELECT name, balance FROM res_partner WHERE balance > 0 LIMIT 5;
SELECT * FROM balance_transaction ORDER BY create_date DESC LIMIT 1;
```

### Test 2 — Betalen met Saldo

1. Voeg een product toe aan de bestelling
2. Selecteer de klant die saldo heeft (zoekicoontje bovenaan)
3. Ga naar het betaalscherm
4. Klik op **"Saldo"** als betaalmethode
5. Verwacht: automatisch ingevuld bedrag (min(saldo, totaal))
6. Klik **"Bevestigen"**
7. Verwacht: order bevestigd, saldo verlaagd

**Verificatie:**
```sql
SELECT balance FROM res_partner WHERE id = <partner_id>;
SELECT * FROM balance_transaction WHERE transaction_type = 'payment' ORDER BY create_date DESC LIMIT 1;
```

### Test 3 — Onvoldoende Saldo (blokkering)

1. Voeg producten toe met totaal > klant saldo
2. Selecteer klant
3. Kies "Saldo" als betaalmethode
4. Verwacht: waarschuwing "Onvoldoende saldo" of automatisch maximum ingevuld
5. Probeer te bevestigen met meer saldo dan beschikbaar
6. Verwacht: betaling geblokkeerd met foutmelding

### Test 4 — Minimum €5 Validatie

1. Open "Saldo" modal
2. Selecteer een klant
3. Vul €3 in als bedrag
4. Klik "Saldo Opladen"
5. Verwacht: foutmelding "Minimum bedrag is €5.00"

### Test 5 — Transactiegeschiedenis controleren

Na de tests:
```bash
docker exec -it kassa_db_1 psql -U odoo -d odoo -c "
SELECT rp.name, bt.amount, bt.transaction_type, bt.payment_method, bt.balance_after, bt.create_date
FROM balance_transaction bt
JOIN res_partner rp ON rp.id = bt.partner_id
ORDER BY bt.create_date DESC LIMIT 10;"
```

---

## 11. Businessregels

| Regel | Implementatie |
|---|---|
| Saldo ≥ 0 altijd | `max(0.0, balance - amount)` in `_process_balance_payment` |
| Minimum top-up €5 | Gecontroleerd in controller én frontend |
| Top-up alleen cash of kaart | Validatie in `topup_balance()` controller |
| Klant verplicht bij saldo betaling | Geblokkeerd in `selectPaymentMethod` patch |
| Saldo controle vóór validatie | Dubbele controle: bij selectie + bij bevestigen |
| Audit trail | Elke mutatie = nieuwe `balance.transaction` record |
| Transacties niet verwijderbaar door kassier | ACL: `perm_unlink=0` voor `group_pos_user` |
