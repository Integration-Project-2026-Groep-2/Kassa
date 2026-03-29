FROM odoo:17

USER root

# Installeer pika voor RabbitMQ communicatie
RUN pip3 install pika

USER odoo
