# Kassa

[![tests](https://github.com/Integration-Project-2026-Groep-2/Kassa/actions/workflows/tests.yml/badge.svg)](https://github.com/Integration-Project-2026-Groep-2/Kassa/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/Integration-Project-2026-Groep-2/Kassa/branch/main/graph/badge.svg)](https://codecov.io/gh/Integration-Project-2026-Groep-2/Kassa)

Kassa is the integration service and POS extension that connects Point-of-Sale (POS) clients with back-end systems (Odoo, RabbitMQ) for transactions, message processing, and cashier logic. This repository contains the Python service (`src/`) and the Odoo add-on (`kassa_pos/`), alongside DevOps scripts and documentation.

Languages & tools: Python, Odoo (XML/JS), Docker, RabbitMQ, pytest, testcontainers

Status: active development — see the `docs/` folder for detailed guides and deployment instructions.

## Contents

- Project overview
- Quickstart (local development with Docker)
- Local development and testing
- Integration tests and CI
- Project structure and important files
- Common tasks & troubleshooting
- Contributing

## Project overview

The repository is mainly split into two areas:

- `src/`: Python service and messaging code (producer, consumer, validators, Odoo integrations)
- `kassa_pos/`: Odoo add-on with POS extensions, controllers, views and data files

Configuration and deployment files (`docker-compose.yml`, `Dockerfile`, `odoo.conf.example`) and detailed documentation are available in `docs/`.

Key features
- POS Top Up payment method and receipt labels
- Standardized VSC endpoint (`/kassa_pos/get_vsc_code`) returning `ok`/`error` JSON responses
- Messaging via RabbitMQ with helper classes in `src/messaging`

See functional and technical details in `docs/README.md` and `docs/KASSA_POS_TOPUP_AND_VSC_CHANGES.md`.

## Quickstart (local with Docker)

1. Requirements
   - Docker Desktop (or Docker Engine)
   - Python 3.11/3.12 + virtualenv (for local tests)
   - Git

2. Copy example config and adjust environment variables if needed

```powershell
cp odoo.conf.example odoo.conf
# Edit .env or use environment overrides as required
```

3. Start services (build & up)

```powershell
docker compose up -d --build
```

4. Wait until Odoo is available (`http://127.0.0.1:8069/health`) and open the POS client in your browser.

Note: if your local Odoo requires a module upgrade (e.g. after a `kassa_pos` version bump), stop the containers, bump the module version or perform the upgrade in Odoo, then restart with `docker compose up -d --build`.

## Local development

1. Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Run unit tests

```powershell
.venv\Scripts\python -m pytest --maxfail=1 -q --cov=src --cov-report=xml
```

3. Integration tests (requires Docker)

Set the environment variable and run all tests (including integration):

```powershell
## $env:RUN_INTEGRATION=1
.venv\Scripts\python -m pytest --maxfail=1 -q --cov=src --cov-report=xml
```

Note: integration tests use `testcontainers` and will start containers such as RabbitMQ; make sure Docker is running.

## CI and coverage

- GitHub Actions workflows (see `.github/workflows`) are used for tests and integration tasks.
- Coverage reports are written to `coverage.xml`. Local runs also generate `coverage.xml`.

Current local coverage (for reference): see the `coverage.xml` file in the repository root.

## Project structure (short)

- `src/` — Python services
  - `connection.py` — Rabbit/Odoo connection helpers
  - `messaging/` — producer/consumer and message builders
  - `settings.py`, `main.py`, `receiver.py` — service entrypoints
- `kassa_pos/` — Odoo module (controllers, models, views, data)
- `docs/` — extensive project documentation (deployment, guides, specs)
- `docker-compose.yml`, `Dockerfile` — development and deployment
- `tests/` — pytest suites (unit and integration)

See the docs in `docs/` for per-topic instructions.

## Common tasks

- Start development containers: `docker compose up -d --build`
- Follow logs: `docker compose logs -f odoo`
- Run unit tests: `.venv\Scripts\python -m pytest -q`
- Rebuild images and re-run: `docker compose up -d --build`

## Troubleshooting

- Docker not reachable: start Docker Desktop and verify with `docker info`.
- Integration tests failing: ensure Docker is running and ports are free; integration tests use `testcontainers`.
- Odoo 401/403 during endpoint tests: check controller `auth` settings (`auth='user'` vs `auth='public'`) and API-token configuration.

## Important documents

- Overview and deployment guides: [docs/README.md](docs/README.md)
- Developer quickstart: [docs/DEVELOPER_QUICKSTART.md](docs/DEVELOPER_QUICKSTART.md)
- POS Top Up & VSC changes: [docs/KASSA_POS_TOPUP_AND_VSC_CHANGES.md](docs/KASSA_POS_TOPUP_AND_VSC_CHANGES.md)
- Docker and environment tips: [docs/DOCKER_KASSA_TEAM.md](docs/DOCKER_KASSA_TEAM.md)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Open a pull request with a clear title and description

Follow repository conventions and use `docs/` for process and release guidance.

## Contact

For questions, support or review requests, please open an issue on GitHub.

