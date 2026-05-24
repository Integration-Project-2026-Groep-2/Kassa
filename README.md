# Kassa

- Tests workflow badge (replace `owner/repo` with your GitHub repository path):

[![tests](https://github.com/Integration-Project-2026-Groep-2/Kassa/actions/workflows/tests.yml/badge.svg)](https://github.com/Integration-Project-2026-Groep-2/Kassa/actions/workflows/tests.yml)

This badge points to the `tests.yml` workflow in the Integration-Project-2026-Groep-2/Kassa repository.

[![codecov](https://codecov.io/gh/Integration-Project-2026-Groep-2/Kassa/branch/main/graph/badge.svg)](https://codecov.io/gh/Integration-Project-2026-Groep-2/Kassa)

## Nieuwigheden

- **Top Up (POS)**: de oude "balance" knop is hernoemd naar **Top Up** en er is een nieuwe "Top Up" betaalmethode toegevoegd aan de POS. Dit zorgt ervoor dat klanten saldo kunnen bijvullen en dat betaalregels duidelijk als "Top Up (gebruik €X.XX)" verschijnen op bonnen en exports.
	- Zie de implementatiedetails in [docs/KASSA_POS_TOPUP_AND_VSC_CHANGES.md](docs/KASSA_POS_TOPUP_AND_VSC_CHANGES.md).
- **VSC endpoint consistentie**: het endpoint `/kassa_pos/get_vsc_code` geeft nu gestandaardiseerd JSON terug met een `ok` veld (`{"ok": true, "vsc_code": "..."}` of `{"ok": false, "error": "..."}`) voor betere foutafhandeling in de frontend.
- **Database / module upgrade**: er zijn fixes toegevoegd om de Top Up betaalmethode ook voor bestaande POS-configuraties beschikbaar te maken (o.a. via XML data bestanden). Bij deployment kan een versie-bump van `kassa_pos` nodig zijn om post-init hooks en data-migraties te laten lopen.

## Kort deploy- en testadvies

1. Bouw en start containers lokaal opnieuw:

```powershell
docker compose up -d --build
```

2. Wacht tot Odoo bereikbaar is en voer een module-upgrade uit (of bump de versie en herstart) zodat de nieuwe data/handlers geladen worden.

3. Hard-refresh de POS-client (Ctrl+F5) en test:
	 - Voer een order uit met een Top Up betaling.
	 - Controleer dat de bon en export de betaalregel tonen als `Top Up (gebruik €X.XX)`.
	 - Controleer in de browser console dat de RPC naar `/kassa_pos/get_vsc_code` een JSON met `ok: true` teruggeeft.

4. Als je problemen ziet met bestaande POS-configuraties, controleer de repo-taken en commits die gerelateerd zijn aan Top Up (bijv. commit-berichten met "Top Up" of "version bump").

## Meer informatie
- Technische beschrijving en aanbevelingen: [docs/KASSA_POS_TOPUP_AND_VSC_CHANGES.md](docs/KASSA_POS_TOPUP_AND_VSC_CHANGES.md)
- Voor vragen of frontend-aanpassingen aan de VSC-responses, geef kort aan welke frontend bestanden aangepast moeten worden en ik help met implementatie en tests.
