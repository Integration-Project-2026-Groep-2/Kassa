FROM odoo:17

USER root

# Installeer RabbitMQ- en XML-afhankelijkheden voor de receiver scripts
COPY requirements.txt /tmp/requirements.txt
RUN apt-get update -qq && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install -r /tmp/requirements.txt || pip3 install --break-system-packages -r /tmp/requirements.txt

# Integreer custom code in de image zodat die zonder bind mounts kan draaien.
COPY kassa_pos /tmp/kassa_pos
COPY src /app/src
COPY setup_rabbitmq.py /app/setup_rabbitmq.py
COPY templates /app/templates
COPY odoo.conf.example /etc/odoo/odoo.conf
COPY docker/odoo-entrypoint.sh /usr/local/bin/odoo-entrypoint.sh

RUN chmod +x /usr/local/bin/odoo-entrypoint.sh \
	&& sed -i 's/\r$//' /usr/local/bin/odoo-entrypoint.sh \
	&& chown -R odoo:odoo /app/src /app/templates /etc/odoo/odoo.conf

# NOTE: Do NOT set PYTHONPATH=/app/src here.
# /app/src contains a subdirectory named 'odoo/' (used by receiver scripts)
# which would shadow the real Odoo package and break Odoo startup with:
#   AttributeError: module 'odoo' has no attribute 'cli'
# Instead, /app/src is added to sys.path at runtime only where needed
# (see user_registration.py) using sys.path.append (not insert) so that
# real packages (odoo, pika, etc.) are always found first.

ENTRYPOINT ["/usr/local/bin/odoo-entrypoint.sh"]

USER root
