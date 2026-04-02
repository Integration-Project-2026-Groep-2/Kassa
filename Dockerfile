FROM odoo:17

USER root

# Installeer pika voor RabbitMQ communicatie
RUN pip3 install pika

# Integreer custom code in de image zodat die zonder bind mounts kan draaien.
COPY kassa_pos /mnt/extra-addons/kassa_pos
COPY src /app/src
COPY templates /app/templates

RUN chown -R odoo:odoo /mnt/extra-addons/kassa_pos /app/src /app/templates

USER odoo
