#!/bin/bash
set -e

cd ~/kassa
docker compose -f docker-compose.production.yml pull odoo
docker compose -f docker-compose.production.yml up -d
docker compose -f docker-compose.production.yml ps
