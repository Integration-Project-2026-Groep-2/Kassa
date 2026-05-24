# Docker for Kassa — Team Deployment Notes

## Overview

This document describes how the Kassa Docker image is built and how to run it in local and team environments.

### Base image
The repository currently uses `odoo:17` as the base image and copies application files into the image. The entrypoint script `docker/odoo-entrypoint.sh` performs module installation/upgrade and other startup tasks.

### Recommended security
- Run the container as non-root where possible
- Limit exposed ports to necessary services (use Nginx proxy)

### Healthcheck
Add a `HEALTHCHECK` instruction to the Dockerfile that probes the local health endpoint or an HTTP endpoint exposed by Odoo. For example:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://127.0.0.1:8069/health || exit 1
```

### Entrypoint
`/usr/local/bin/odoo-entrypoint.sh` is the canonical entrypoint and handles copying modules, running migrations and invoking the Odoo server.
