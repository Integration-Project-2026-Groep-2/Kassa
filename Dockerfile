FROM odoo:17

USER root

# Installeer RabbitMQ- en XML-afhankelijkheden voor de receiver scripts
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt || pip3 install --break-system-packages -r /tmp/requirements.txt

# Integreer custom code in de image zodat die zonder bind mounts kan draaien.
COPY kassa_pos /mnt/extra-addons/kassa_pos
COPY src /app/src
COPY setup_rabbitmq.py /app/setup_rabbitmq.py
COPY templates /app/templates
COPY odoo.conf /etc/odoo/odoo.conf
COPY docker/odoo-entrypoint.sh /usr/local/bin/odoo-entrypoint.sh

RUN chmod +x /usr/local/bin/odoo-entrypoint.sh \
	&& sed -i 's/\r$//' /usr/local/bin/odoo-entrypoint.sh \
	&& chown -R odoo:odoo /mnt/extra-addons/kassa_pos /app/src /app/templates /etc/odoo/odoo.conf

ENTRYPOINT ["/usr/local/bin/odoo-entrypoint.sh"]

USER root
