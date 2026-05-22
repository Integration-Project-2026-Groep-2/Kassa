# CRM Team - Gebruikeraanmaak Integratie met Kassa (v1.9)

## Doel
Deze documentatie beschrijft de geïntegreerde werkstroom tussen CRM en Kassa voor gebruikeraanmaak, gebaseerd op de huidige implementatie en XML-contracten (AsyncAPI/XML v1.8.0+).

## Korte Samenvatting
De integratie volgt dit patroon:

1. **Kassa publiceert** een nieuw gebruikersprofiel naar de `kassa.user.created` wachtrij als XML `User`
2. **CRM verbruikt** het bericht en maakt of verrijkt de gebruiker in CRM
3. **CRM bevestigt** door XML `UserConfirmed` naar de `crm.user.confirmed` wachtrij te publiceren
4. **Kassa verwerkt** de bevestiging en synchroniseert de lokale gebruikersopslag

---

## RabbitMQ Routes

| Richting | Doel | Exchange | Routing Key | Wachtrij | Durable |
|---|---|---|---|---|---|
| Kassa → CRM | Gebruiker create event | default `''` | `kassa.user.created` | `kassa.user.created` | true |
| CRM → Kassa | Gebruiker bevestiging | default `''` | `crm.user.confirmed` | `crm.user.confirmed` | true |
| CRM → Kassa | Gebruiker update | default `''` | `crm.user.updated` | `crm.user.updated` | true |
| CRM → Kassa | Gebruiker gedeactiveerd | default `''` | `crm.user.deactivated` | `crm.user.deactivated` | true |

**Opmerking:** Berichten worden rechtstreeks naar wachtrijen gepubliceerd via de default exchange. Routing key is gelijk aan wachtrijnaam.

---

## Stap 1 - Wat CRM Ontvangt bij Gebruikeraanmaak

**Berichttype:** `User`  
**Wachtrij:** `kassa.user.created`

### XML-formaat (Voorbeeld)

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

| Veld | Verplicht | Type | Beschrijving |
|---|---|---|---|
| userId | Ja | UUID v4 | Unieke identificatie voor gebruiker |
| firstName | Ja | String(100) | Voornaam van gebruiker |
| lastName | Ja | String(100) | Achternaam van gebruiker |
| email | Ja | String(255) | E-mailadres |
| companyId | Nee | UUID v4 | UUID van gekoppeld bedrijf |
| badgeCode | Ja | String(50) | Badge- of QR-code identificatie |
| role | Ja | Enum | Rol (VISITOR, CASHIER, ADMIN, MANAGER) |
| createdAt | Nee | ISO 8601 | Aanmaaktijd (UTC) |
| updatedAt | Nee | ISO 8601 | Laatste wijzigingstijd (UTC) |

---

## Stap 2 - Wat CRM Terug Moet Sturen als Bevestiging

**Berichttype:** `UserConfirmed` (Contract 13)  
**Wachtrij:** `crm.user.confirmed`

### XML-formaat (Voorbeeld)

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

| Veld | Verplicht | Type | Opmerkingen |
|---|---|---|---|
| id | Ja | UUID v4 | Moet gelijk zijn aan userId uit User bericht |
| email | Ja | String(255) | E-mailadres van gebruiker |
| firstName | Ja | String(100) | Voornaam |
| lastName | Ja | String(100) | Achternaam |
| role | Ja | Enum | VISITOR, CASHIER, ADMIN, MANAGER |
| isActive | Ja | Boolean | Actieve status in CRM |
| gdprConsent | Ja | Boolean | GDPR-toestemmingsvlag |
| confirmedAt | Ja | ISO 8601 UTC | Bevestigingsmoment (bijv. 2026-04-22T10:00:02Z) |
| phone | Nee | String(20) | Telefoonnummer |
| companyId | Nee | UUID v4 | Bedrijfs-ID |
| badgeCode | Nee | String(50) | Badge-code (aanbevolen voor sync) |

**Kritisch:**
- `id` moet exact gelijk zijn aan `userId` uit het User-bericht
- `role` moet een geldige contract enum-waarde zijn
- `confirmedAt` moet ISO 8601 UTC zijn met Z-suffix

---

## Veldtoewijzing: Kassa User ↔ CRM UserConfirmed

| Kassa User | CRM UserConfirmed | Opmerkingen |
|---|---|---|
| userId | id | Moet gedurende hele levenscyclus identiek blijven |
| firstName | firstName | 1:1 toewijzing |
| lastName | lastName | 1:1 toewijzing |
| email | email | 1:1 toewijzing |
| role | role | Moet contract-compatibele enum zijn |
| companyId | companyId | Optioneel maar aanbevolen voor bedrijfsgekoppelde gebruikers |
| badgeCode | badgeCode | Optioneel in UserConfirmed; aanbevolen voor POS-sync |
| createdAt | — | Kassa intern; confirmedAt weerspiegelt CRM-bevestiging |
| — | isActive | CRM stelt gebruikersstatus actief in |
| — | gdprConsent | CRM beheert GDPR-vlag |

---

## Aanbevolen End-to-End Werkstroom

1. **Verbruik** wachtrij `kassa.user.created`
2. **Valideer** XML-schema en verplichte velden
3. **Zoeken of aanmaken** gebruiker in CRM-database
4. **Verrijk** gebruiker (stel isActive, gdprConsent, etc. in)
5. **Publiceer** `UserConfirmed` naar wachtrij `crm.user.confirmed`
6. **Voor updates:** Publiceer `UserUpdated` naar wachtrij `crm.user.updated`
7. **Voor deactivering:** Publiceer `UserDeactivated` naar wachtrij `crm.user.deactivated`

---

## Idempotentie & Retry-verwerking

### Idempotentie
Gebruik `id`/`userId` als idempotentie-sleutel in CRM. Dit zorgt ervoor dat dubbele afleveringen geen dubbele gebruikers aanmaken.

**Aanbevolen logica:**
```python
def process_user(user_id, **kwargs):
    user = CRM.User.find_or_create(id=user_id)
    user.update(**kwargs)
    return user
```

### Retry-gedrag
Als Kassa tijdelijk niet naar CRM kan publiceren:
- Berichten worden opgeslagen in een **lokale fallback-wachtrij** in Odoo
- Wanneer CRM herstelt, stuurt Kassa hangende berichten opnieuw
- De idempotentie-sleutel van CRM voorkomt dubbele verwerking

---

## Validatiebronnen

Raadpleeg deze bestanden als bron van waarheid:

- `src/schema/kassa-schema-v1.xsd` — Hoofd-XML-schema
- `src/schema/contracts/` — Individuele contractdefinities
- `src/tests/test_xml_validator.py` — Validatietestsuite
- `src/messaging/user_consumer.py` — CRM-consumerreferentie
- `src/messaging/consumer.py` — Kassa-consumerreferentie
- `kassa_pos/models/user_registration.py` — Kassa-gebruikersmodel
- `kassa_pos/models/res_partner.py` — Partner (bedrijf) koppeling

---

## POS-betaalmethoden (Huidige Status)

**Opmerking:** De betaalmethode "Top Up" heet nu **"Saldo"** in de betaalmethodenlijst.

| Betaalmethode | Code | Journal | Doel |
|---|---|---|---|
| Contant | KCASH | account_journal_cash_kassa | Contante betaling ter plaatse |
| Bancontact | KBANC | account_journal_bancontact_kassa | Kaartbetaling |
| Factuur | — | — | Bedrijfsfacturering (vereist company_id_custom koppeling) |
| **Saldo** | KSAL | account_journal_saldo_kassa | Gebruikerssaldo aanvulling |

---

## Interoperabiliteit Checklist

- [ ] Wachtrij `kassa.user.created` bestaat en is durable
- [ ] Wachtrij `crm.user.confirmed` bestaat en is durable
- [ ] CRM antwoordt met geldige `UserConfirmed` XML (geen vrij-formaat XML)
- [ ] `id` in `UserConfirmed` gelijk aan `userId` uit `User`
- [ ] Alle XML-timestamps zijn ISO 8601 UTC met `Z`-suffix
- [ ] CRM verwerkt dubbele afleveringen idempotent
- [ ] `role` enum-waarden komen overeen met contractdefinities
- [ ] `companyId` wordt gevalideerd als UUID v4 indien aanwezig
- [ ] Badge-code is uniek binnen Kassa-systeem

---

## Probleemoplossing

### Gebruiker verschijnt niet in Kassa na aanmaak

**Controleer:**
1. Is `UserConfirmed` gepubliceerd naar wachtrij `crm.user.confirmed`?
2. Is XML geldig tegen `kassa-schema-v1.xsd`?
3. Is `id` een geldige UUID v4?
4. Is `role` een geldige enum-waarde (VISITOR, CASHIER, ADMIN, MANAGER)?
5. Zijn er fouten in Kassa-logs? (Controleer RabbitMQ-consumerlogs.)

### UserCreated bereikt CRM niet

**Controleer:**
1. Wachtrij `kassa.user.created` bestaat en is durable
2. CRM-consumer is verbonden met juiste RabbitMQ vhost/referenties
3. RabbitMQ-gebruiker heeft `read` toestemming op wachtrij
4. XML-schema validatie slaagt (gebruik `src/tests/test_xml_validator.py`)
5. Indien CRM omlaag is, controleer Kassa's fallback-wachtrij op hangende berichten

### Betaalmethode Factuur blokkeert gebruiker zonder bedrijf

**Verwacht gedrag:**
- Gebruiker probeert via "Factuur" betaalmethode te betalen
- Serverzijdige guard controleert `company_id_custom` veld
- Indien ontbreekt, retourneert fout: "Gebruiker niet gekoppeld aan een bedrijf"
- Client geeft gestileerde foutmelding weer

**Controleer:**
- Veld `company_id_custom` van Partner is ingevuld voor gebruikers die factuur kunnen gebruiken
- UserConfirmed bevat `companyId` wanneer bedrijf vereist is

### Dubbele gebruikers aangemaakt in CRM

**Oplossing:**
- Implementeer idempotentie-sleutel op `User.id` veld
- Roep altijd `find_or_create(id=...)` aan voordat u aanmaakt
- Maak gebruikers nooit alleen op basis van e-mail aan

---

## Codereferenties (Bijgewerkt)

### Kassa-gebruikersregistratiemodel
**Bestand:** `kassa_pos/models/user_registration.py`
- Verwerkt gebruikeraanmaak vanuit UI
- Publiceert User-bericht naar `kassa.user.created`

### Kassa-gebruikersconsumer
**Bestand:** `src/messaging/user_consumer.py`
- Verbruikt UserConfirmed uit `crm.user.confirmed`
- Werkt lokale gebruikersopslag bij met CRM-respons

### CRM-consumer (Referentie)
**Bestand:** `src/messaging/consumer.py`
- Luistert op wachtrij `kassa.user.created`
- Valideert en verwerkt User-berichten

### POS-order & Factureringslogica
**Bestand:** `kassa_pos/models/pos_order.py`
- Serverzijdige guard: blokkeert Factuur-betaling als `company_id_custom` ontbreekt
- Retourneert UserError met bericht "Gebruiker niet gekoppeld aan een bedrijf"

### Partnermodel (Bedrijfskoppeling)
**Bestand:** `kassa_pos/models/res_partner.py`
- Definieert `company_id_custom` veld voor bedrijfskoppeling
- Gebruikt voor geschiktheid van Factuur-betaling

---

## Versiegeschiedenis

| Versie | Datum | Wijzigingen |
|---|---|---|
| 1.9 | 2026-05-13 | Bijgewerkt naamgeving betaalmethode (Top Up → Saldo); toegevoegde POS-betaalmethodentabel; verduidelijkte Factuur-betaalbeveiligingslogica |
| 1.8 | 2026-04-22 | Initiële uitgebreide documentatie |

---

## Contact & Ondersteuning

Voor integratievragen of schema-updates verwijzen naar:
- Architectuurdocs: `docs/ARCHITECTURE.md`
- API-docs: `docs/POS_USER_REGISTRATION_API.md`
- Implementatiehandleiding: `docs/AZURE_DEPLOYMENT_GUIDE.md`
