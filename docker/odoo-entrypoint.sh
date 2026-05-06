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
ODOO_SYNC_MODULES="${ODOO_SYNC_MODULES:-}"
ODOO_SKIP_MODULE_SYNC="${ODOO_SKIP_MODULE_SYNC:-false}"

# This ensures the volume always has the latest code from the image.
# We check if it's a mountpoint to avoid "Device or resource busy" errors with bind mounts.
if ! mountpoint -q /mnt/extra-addons/kassa_pos/; then
  rm -rf /mnt/extra-addons/kassa_pos/
  mkdir -p /mnt/extra-addons/kassa_pos/
  cp -r /tmp/kassa_pos/. /mnt/extra-addons/kassa_pos/
fi
chown -R odoo:odoo /mnt/extra-addons/kassa_pos/

# kassa_pos is always required — merge it with any extra modules from ODOO_SYNC_MODULES.
# This ensures the addon is installed/upgraded on every start, regardless of env config.
  EFFECTIVE_SYNC_MODULES="${CORE_MODULES},${ODOO_SYNC_MODULES}"
# Ensure Top Up payment method is linked to Kassa Main pos_config
echo "[entrypoint] Linking Top Up payment method to pos_config"
psql \
  "postgresql://${ODOO_DB_USER}:${ODOO_DB_PASSWORD}@${ODOO_DB_HOST}:${ODOO_DB_PORT}/${ODOO_DB_NAME}" \
  -c "INSERT INTO pos_config_pos_payment_method_rel (pos_config_id, pos_payment_method_id) SELECT pc.id, ppm.id FROM pos_config pc, pos_payment_method ppm WHERE pc.name LIKE '%Kassa Main%' AND ppm.name LIKE '%Top Up%' ON CONFLICT DO NOTHING;" 2>/dev/null || true

# Initialize RabbitMQ topology (exchanges, queues, bindings)
echo "[entrypoint] Initializing RabbitMQ topology via setup_rabbitmq.py"
else
  EFFECTIVE_SYNC_MODULES="${CORE_MODULES}"
fi

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

RECEIVER_ENABLED="${ENABLE_RECEIVER_IN_ODOO_IMAGE:-true}"
REC_PID=""

cleanup() {
  if [ -n "$HB_PID" ]; then
    kill "$HB_PID" 2>/dev/null || true
  fi
  if [ -n "$REC_PID" ]; then
    kill "$REC_PID" 2>/dev/null || true
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

if [ "$ODOO_SKIP_MODULE_SYNC" != "true" ] && [ -n "$ODOO_DB_NAME" ]; then

  # Check if kassa_pos is already installed in the database.
  # If not → run -i (fresh install). If yes → only upgrade modules
  # explicitly listed in ODOO_SYNC_MODULES (deliberate upgrades only).
  # This prevents re-applying data files on every restart of an existing DB.
  KASSA_INSTALLED=$(psql \
    "postgresql://${ODOO_DB_USER}:${ODOO_DB_PASSWORD}@${ODOO_DB_HOST}:${ODOO_DB_PORT}/${ODOO_DB_NAME}" \
    -tAc "SELECT state FROM ir_module_module WHERE name='kassa_pos' LIMIT 1" \
    2>/dev/null || echo "")

  BASE_SYNC_ARGS=(
    odoo
    --config=/etc/odoo/odoo.conf
    --db_host="${ODOO_DB_HOST}"
    --db_port="${ODOO_DB_PORT}"
    --db_user="${ODOO_DB_USER}"
    --db_password="${ODOO_DB_PASSWORD}"
    --db-filter="${ODOO_DB_FILTER}"
    --http-port="${ODOO_HTTP_PORT}"
    --proxy-mode
    --log-level="${ODOO_LOG_LEVEL}"
    -d "${ODOO_DB_NAME}"
    --stop-after-init
  )

  if [ "$KASSA_INSTALLED" != "installed" ]; then
    echo "[entrypoint] kassa_pos not installed (state='${KASSA_INSTALLED}'), running install: ${EFFECTIVE_SYNC_MODULES}"
    SYNC_CMD=("${BASE_SYNC_ARGS[@]}" -i "${EFFECTIVE_SYNC_MODULES}" --without-demo=all)
    if [ "$(id -u)" = "0" ]; then
      runuser -u odoo -- "${SYNC_CMD[@]}"
    else
      "${SYNC_CMD[@]}"
    fi
  else
    # Always upgrade kassa_pos to ensure data files are loaded (pos_config_data.xml, etc.)
    # Also upgrade any modules explicitly listed in ODOO_SYNC_MODULES
    MODULES_TO_UPGRADE="kassa_pos"
    if [ -n "$ODOO_SYNC_MODULES" ]; then
      MODULES_TO_UPGRADE="${MODULES_TO_UPGRADE},${ODOO_SYNC_MODULES}"
    fi
    echo "[entrypoint] kassa_pos already installed, upgrading for data sync: ${MODULES_TO_UPGRADE}"
    SYNC_CMD=("${BASE_SYNC_ARGS[@]}" -u "${MODULES_TO_UPGRADE}")
    if [ "$(id -u)" = "0" ]; then
      runuser -u odoo -- "${SYNC_CMD[@]}"
    else
      "${SYNC_CMD[@]}"
    fi
  fi
fi

# Initialize RabbitMQ topology (exchanges, queues, bindings)
echo "[entrypoint] Initializing RabbitMQ topology via setup_rabbitmq.py"
if [ "$(id -u)" = "0" ]; then
  runuser -u odoo -- python3 /app/setup_rabbitmq.py || {
    echo "[entrypoint] WARNING: RabbitMQ setup failed, but continuing with Odoo startup"
  }
else
  python3 /app/setup_rabbitmq.py || {
    echo "[entrypoint] WARNING: RabbitMQ setup failed, but continuing with Odoo startup"
  }
fi

if [ "$HEARTBEAT_ENABLED" = "true" ]; then
  (
    cd /app/src
    python3 main_heartbeat.py
  ) &
  HB_PID="$!"
  echo "[entrypoint] Heartbeat gestart in dezelfde container (PID: ${HB_PID})"
fi

if [ "$RECEIVER_ENABLED" = "true" ]; then
  (
    cd /app/src
    python3 main.py
  ) &
  REC_PID="$!"
  echo "[entrypoint] Contact receiver gestart in dezelfde container (PID: ${REC_PID})"
fi

echo "[entrypoint] Odoo starten met custom config en flags"
if [ "$(id -u)" = "0" ]; then
  exec runuser -u odoo -- "$@"
fi

exec "$@"