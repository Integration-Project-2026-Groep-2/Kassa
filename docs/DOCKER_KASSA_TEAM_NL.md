# Docker - Container & Deployment
## Docker - Kassa Team
Integration Project 2025/2026 | Groep 2  
Auteur: Shemsedine Boughaleb | Versie: 1.1 | Maart 2026

## Inhoudsopgave
1. Wat draait er in onze container
2. Image vs container
3. Dockerfile
4. docker-compose.yml
5. Omgevingsvariabelen
6. Lokaal opstarten
7. Debuggen
8. Deployen naar de Azure VM
9. Architectuurbeslissingen
10. Bekende beperkingen en afhankelijkheden

---

## 1. Wat draait er in onze container

Odoo POS is de operationele kassatoepassing. Onze container bevat uitsluitend de integratiecode van Team Kassa: vier asyncio-taken die gelijktijdig draaien in één Python-proces.

| Taak | Verantwoordelijkheid |
|---|---|
| `heartbeat.py` | Stuurt elke seconde een XML-bericht naar `kassa.heartbeat` |
| `status.py` | Publiceert periodiek CPU-, geheugen- en schijfbelasting naar `kassa.status.checked` |
| `receiver.py` | Luistert op de queues die voor Kassa relevant zijn |
| `sender.py` | Publiceert events vanuit Kassa/Odoo naar RabbitMQ |

De container biedt geen HTTP API aan en host geen RabbitMQ. RabbitMQ draait op de Infra-omgeving.

### Queues waarop wij luisteren (receiver)

| Queue | Van | Contract | Release |
|---|---|---:|---|
| `controlroom.warning.issued` | Controlroom | 9 | R1 |
| `crm.person.lookup.responded` | CRM | 10b | R1 |
| `crm.user.confirmed` | CRM | 13 | R1 |
| `crm.company.confirmed` | CRM | 14 | R1 |
| `crm.unpaid.responded` | CRM | 17b | R1 |
| `crm.user.updated` | CRM | 18 | R2 |
| `crm.company.updated` | CRM | 19 | R2 |
| `crm.user.deactivated` | CRM | 22 | R3 |
| `crm.company.deactivated` | CRM | 23 | R3 |

### Events die wij publiceren (sender)

| Queue / Exchange | Naar | Contract | Release |
|---|---|---:|---|
| `kassa.heartbeat` | Controlroom | 7 | R1 |
| `kassa.status.checked` | Controlroom | 8 | R1 |
| `kassa.person.lookup.requested` | CRM | 10a | R1 |
| `kassa.payment.confirmed` | CRM | 16 | R1 |
| `kassa.unpaid.requested` | CRM | 17a | R1 |
| `kassa.invoice.requested` | Facturatie | K-01 | R1 |

Belangrijk voor request/response: inkomende requests bevatten een `requestId` in de payload. De receiver moet deze `requestId` meesturen in de response zodat de verzender de response aan het originele request kan koppelen.

---

## 2. Image vs container

```text
Dockerfile --[docker build]--> Image --[docker run]--> Container
```

Een image is een onveranderlijk snapshot van de applicatie. Een container is een draaiende instantie van die image. Bij elke codewijziging moet je een nieuwe image bouwen.

---

## 3. Dockerfile

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Dependencies als aparte laag -- betere build cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# Non-root user -- standaard security vereiste
RUN adduser --disabled-password --gecos "" appuser
USER appuser

# Docker healthcheck -- onafhankelijk van de RabbitMQ heartbeat
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD python -c "import sys; sys.exit(0)"

CMD ["python", "src/main.py"]
```

### Belangrijke opmerkingen

**Vereist bestand:** `src/schema/kassa-schema-v1.xsd` moet aanwezig zijn in de repo. `xml_validator.py` laadt dit bestand bij opstart. Ontbreekt het, dan crasht de container direct.

**Waarom dependencies voor broncode kopiëren:** Docker cachet elke laag apart. Zolang `requirements.txt` niet wijzigt, slaat Docker de `pip install`-laag over bij een rebuild.

**Waarom non-root:** Een container die als root draait heeft bij een security-incident dezelfde rechten als root op de host. We draaien als appuser.

**Verschil healthcheck en heartbeat:** De Docker healthcheck controleert of het Python-proces nog reageert - voor Docker zelf en voor Infra. De heartbeat in `heartbeat.py` is een XML-bericht op de RabbitMQ queue voor het Controlroom-dashboard. Beide zijn nodig en staan los van elkaar.

---

## 4. docker-compose.yml

Bedoeld voor lokale development. Start onze container en optioneel een lokale RabbitMQ-instantie.

```yaml
services:
  kassa:
    build: .
    container_name: kassa
    restart: unless-stopped
    env_file:
      - .env
    depends_on:
      rabbitmq:
        condition: service_healthy

  rabbitmq:
    image: rabbitmq:3.13-management
    ports:
      - "5672:5672"
      - "15672:15672"
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
```

In productie staat RabbitMQ al op de Infra-omgeving. De rabbitmq service vervalt dan en je overschrijft `RABBITMQ_URL` in `.env` met het productieadres.

---

## 5. Omgevingsvariabelen

Credentials staan nooit in de code of in Git. Ze worden doorgegeven via `.env`.

Kopieer `.env.example` naar `.env` en vul in.

```bash
cp .env.example .env
```

`.env` staat in `.gitignore`. Elk teamlid maakt zijn eigen `.env` aan op basis van `.env.example`.

---

## 6. Lokaal opstarten

### Vereisten
- Docker Desktop geïnstalleerd en draaiend
- Windows: WSL2 is verplicht
- `docker --version` en `docker compose version` moeten een versienummer teruggeven

### Opstartproces

```bash
# .env aanmaken
cp .env.example .env

# Vul .env in met Odoo- en RabbitMQ-credentials

# Opstarten
docker compose up --build
```

### Handige commando's

```bash
# Logs live bekijken
docker compose logs -f kassa

# Containerstatus
docker compose ps

# Stoppen
docker compose down

# Alleen image herbouwen
docker compose build
```

---

## 7. Debuggen

### Logs bekijken

```bash
# Live logs
docker compose logs -f kassa

# Laatste 100 regels
docker compose logs --tail=100 kassa
```

### In de draaiende container gaan

```bash
docker compose exec kassa sh
```

Handig om te controleren of bestanden aanwezig zijn of environment variables correct zijn geladen:

```bash
# Binnen de container:
echo $RABBITMQ_URL
echo $ODOO_URL
ls src/
```

### Healthcheck-status opvragen

```bash
docker inspect --format='{{json .State.Health}}' kassa
```

Geeft `healthy`, `unhealthy` of `starting` terug.

### RabbitMQ management UI lokaal

```
http://localhost:15672
```

Login: `guest` / `guest`

### LOG_LEVEL verhogen voor meer detail

- Zet `LOG_LEVEL=DEBUG` in `.env`
- Herstart de container

---

## 8. Deployen naar de Azure VM

### Infra-richtlijnen

De Ubuntu VM draait op Azure. SSH verloopt via poort 60022.

### Reverse proxy en routes

Voor Team Kassa is het belangrijke punt dat de omgeving via een reverse proxy werkt. Externe poorten hoeven daarom in principe niet apart opengezet te worden.

### Externe poort-range indien toch nodig

Als er toch met aparte externe poorten gewerkt wordt, is voor Team Kassa deze range voorzien.

### Verbinden

```bash
ssh -p 60022 ehbstudent@integrationproject-2526s2-dag02.westeurope.cloudapp.azure.com
```

### Manueel deployen

```bash
ssh -p 60022 ehbstudent@integrationproject-2526s2-dag02.westeurope.cloudapp.azure.com
cd /pad/naar/kassa   # af te stemmen met Infra
git pull origin prod
docker compose up --build -d
docker compose logs -f kassa
```

De `.env` op de VM bevat de productiecredentials en wordt niet overschreven bij een deploy.

---

## 9. Architectuurbeslissingen

### Waarom 1 container

De vier taken draaien als asyncio-taken in één proces. Alternatief was meerdere aparte containers. Gekozen voor 1 container omdat de overhead van meerdere containers niet opweegt tegen de voordelen op deze projectschaal.

### Waarom aio-pika en niet pika

`pika` is blocking: terwijl het wacht op een RabbitMQ-bericht staat de thread stil. Met `aio-pika` draaien heartbeat, status, receiver en sender gelijktijdig. De heartbeat moet elke seconde vuren ongeacht wat de receiver doet.

### Waarom python:3.13-slim

De slim-variant beperkt imagegrootte en aanvalsoppervlak.

### Waarom Odoo buiten deze integratiecontainer blijft

De rol van deze container is messaging en integratie. Odoo POS zelf is de operationele applicatie. Door de integratiecode los te houden, kunnen queue-logica, validatie en monitoring apart beheerd worden.

---

## 10. Bekende beperkingen en afhankelijkheden

*(Sectie in voorbereiding - neem contact op met Team Kassa voor actuele beperkingen)*
