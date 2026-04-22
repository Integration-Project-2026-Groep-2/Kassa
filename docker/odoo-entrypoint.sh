#!/usr/bin/env bash
set -euo pipefail

ODOO_DB_HOST="${DB_HOST:-${HOST:-db}}"
ODOO_DB_PORT="${DB_PORT:-5432}"
ODOO_DB_USER="${POSTGRES_USER:-${USER:-odoo}}"
ODOO_DB_PASSWORD="${POSTGRES_PASSWORD:-${PASSWORD:-odoo}}"
ODOO_DB_NAME="${POSTGRES_DB:-odoo}"
ODOO_HTTP_PORT="${ODOO_PORT:-8069}"
ODOO_LONGPOLLING_PORT="${ODOO_LONGPOLLING_PORT:-8072}"
ODOO_DATA_DIR="${ODOO_DATA_DIR:-/var/lib/odoo}"
ODOO_SESSION_DIR="${ODOO_SESSION_DIR:-${ODOO_DATA_DIR}/sessions}"
ODOO_LOG_LEVEL_RAW="${LOG_LEVEL:-info}"
ODOO_LOG_LEVEL="$(printf '%s' "$ODOO_LOG_LEVEL_RAW" | tr '[:upper:]' '[:lower:]')"
ODOO_DB_FILTER="${ODOO_DB_FILTER:-^${ODOO_DB_NAME}$}"

case "$ODOO_LOG_LEVEL" in
  info|debug_rpc|warn|test|critical|runbot|debug_sql|error|debug|debug_rpc_answer|notset)
    ;;
  *)
    echo "[entrypoint] Ongeldige LOG_LEVEL='${ODOO_LOG_LEVEL_RAW}', fallback naar 'info'"
    ODOO_LOG_LEVEL="info"
    ;;
esac

if [ "$(id -u)" = "0" ]; then
  mkdir -p "$ODOO_DATA_DIR" "$ODOO_SESSION_DIR"
  chown -R odoo:odoo "$ODOO_DATA_DIR" "$ODOO_SESSION_DIR"
  chmod 700 "$ODOO_SESSION_DIR"
fi

ODOO_HELP_OUTPUT="$(odoo --help 2>&1 || true)"
ODOO_REALTIME_PORT_ARG=""

if echo "$ODOO_HELP_OUTPUT" | grep -q -- "--longpolling-port"; then
  ODOO_REALTIME_PORT_ARG="--longpolling-port=${ODOO_LONGPOLLING_PORT}"
elif echo "$ODOO_HELP_OUTPUT" | grep -q -- "--gevent-port"; then
  ODOO_REALTIME_PORT_ARG="--gevent-port=${ODOO_LONGPOLLING_PORT}"
else
  echo "[entrypoint] Geen ondersteunde realtime poort flag gevonden; ga verder zonder expliciete realtime poort argument"
fi

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
  --db-filter="${ODOO_DB_FILTER}" \
  --http-port="${ODOO_HTTP_PORT}" \
  --proxy-mode \
  --log-level="${ODOO_LOG_LEVEL}"

if [ -n "${ODOO_REALTIME_PORT_ARG}" ]; then
  set -- "$@" "${ODOO_REALTIME_PORT_ARG}"
fi

if [ -n "${ODOO_DB_NAME:-}" ]; then
  set -- "$@" -d "${ODOO_DB_NAME}"
fi

if [ -n "${ODOO_EXTRA_ARGS:-}" ]; then
  # shellcheck disable=SC2086
  set -- "$@" ${ODOO_EXTRA_ARGS}
fi

echo "[entrypoint] Odoo starten met custom config en flags"
if [ "$(id -u)" = "0" ]; then
  exec runuser -u odoo -- "$@"
fi

exec "$@"