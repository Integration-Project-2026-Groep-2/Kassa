# Secrets Rotation Runbook

Steps to rotate any exposed credentials found in the repository or local `.env`:

1. Identify secrets to rotate (DB passwords, RabbitMQ creds, API keys).
2. Revoke and rotate secrets in the services (Postgres, RabbitMQ, cloud providers).
3. Update deployment configuration (Docker secrets, Kubernetes Secrets, CI variables).
4. Remove secrets from local `.env` files and replace with placeholders.
5. Inform stakeholders and update the incident log.

Removing secrets from Git history (non-destructive suggestion):
- Do not rewrite history unless necessary. If necessary, use `git filter-repo` on a local clone and force-push.

Contact: security@yourorg.example
