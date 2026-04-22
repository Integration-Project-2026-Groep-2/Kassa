#!/usr/bin/env bash
set -euo pipefail

ODOO_DB_HOST="${DB_HOST:-${HOST:-db}}"
ODOO_DB_PORT="${DB_PORT:-5432}"
ODOO_DB_USER="${POSTGRES_USER:-${USER:-odoo}}"
ODOO_DB_PASSWORD="${POSTGRES_PASSWORD:-${PASSWORD:-odoo}}"
ODOO_DB_NAME="${POSTGRES_DB:-odoo}"
ODOO_HTTP_PORT="${ODOO_PORT:-8069}"
ODOO_LONGPOLLING_PORT="${ODOO_LONGPOLLING_PORT:-8072}"
ODOO_LOG_LEVEL="${LOG_LEVEL:-info}"
ODOO_DB_FILTER="${ODOO_DB_FILTER:-^${ODOO_DB_NAME}$}"

HEARTBEAT_ENABLED="${ENABLE_HEARTBEAT_IN_ODOO_IMAGE:-true}"
HB_PID=""

if [ "$HEARTBEAT_ENABLED" = "true" ]; then
  (
    cd /app/src
    python3 main_heartbeat.py
  ) &
  HB_PID="$!"
  echo "[entrypoint] Heartbeat gestart in dezelfde container (PID: ${HB_PID})"
fi

cleanup() {
  if [ -n "$HB_PID" ]; then
    kill "$HB_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT TERM INT

set -- \
  odoo \
  --config=/etc/odoo/odoo.conf \
  --db_host="${ODOO_DB_HOST}" \
  --db_port="${ODOO_DB_PORT}" \
  --db_user="${ODOO_DB_USER}" \
  --db_password="${ODOO_DB_PASSWORD}" \
  --db_name="${ODOO_DB_NAME}" \
  --db-filter="${ODOO_DB_FILTER}" \
  --http-port="${ODOO_HTTP_PORT}" \
  --longpolling-port="${ODOO_LONGPOLLING_PORT}" \
  --proxy-mode \
  --log-level="${ODOO_LOG_LEVEL}"

if [ -n "${ODOO_EXTRA_ARGS:-}" ]; then
  # shellcheck disable=SC2086
  set -- "$@" ${ODOO_EXTRA_ARGS}
fi

echo "[entrypoint] Odoo starten met custom config en flags"
"$@"
