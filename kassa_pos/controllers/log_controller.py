# -*- coding: utf-8 -*-

import json
import logging
import os
import re
from datetime import datetime, timezone

from odoo import http

_logger = logging.getLogger(__name__)

_VALID_LEVELS = {"DEBUG", "INFO", "WARN", "ERROR", "FATAL", "PANIC"}
_XML_CTRL_CHARS = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")


def _rabbit_params():
    import pika
    credentials = pika.PlainCredentials(
        os.environ.get("RABBIT_USER", "guest"),
        os.environ.get("RABBIT_PASSWORD", "guest"),
    )
    return pika.ConnectionParameters(
        host=os.environ.get("RABBIT_HOST", "localhost"),
        port=int(os.environ.get("RABBIT_PORT", "5672")),
        virtual_host=os.environ.get("RABBIT_VHOST", "/"),
        credentials=credentials,
        connection_attempts=2,
        retry_delay=1,
        socket_timeout=3,
    )


def _publish_log_event(level: str, data: str) -> None:
    try:
        from lxml import etree
        root = etree.Element("LogEvent")
        etree.SubElement(root, "level").text = level
        etree.SubElement(root, "timestamp").text = datetime.now(timezone.utc).isoformat()
        etree.SubElement(root, "service").text = "KASSA-POS"
        etree.SubElement(root, "data").text = _XML_CTRL_CHARS.sub("?", data)
        xml_bytes = etree.tostring(root, xml_declaration=True, encoding="UTF-8")
    except ImportError:
        import xml.etree.ElementTree as ET
        root = ET.Element("LogEvent")
        ET.SubElement(root, "level").text = level
        ET.SubElement(root, "timestamp").text = datetime.now(timezone.utc).isoformat()
        ET.SubElement(root, "service").text = "KASSA-POS"
        ET.SubElement(root, "data").text = _XML_CTRL_CHARS.sub("?", data)
        xml_bytes = ET.tostring(root, encoding="UTF-8", xml_declaration=True)

    import pika
    params = _rabbit_params()
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.exchange_declare(exchange="logs.direct", exchange_type="direct", durable=True)
    channel.basic_publish(
        exchange="logs.direct",
        routing_key="routing.log",
        body=xml_bytes,
        properties=pika.BasicProperties(
            delivery_mode=2,
            content_type="application/xml",
        ),
    )
    connection.close()


class LogController(http.Controller):

    @http.route("/kassa/log", type="http", auth="public", methods=["POST"], csrf=False)
    def receive_log(self, **kwargs):
        try:
            body = http.request.httprequest.get_data(as_text=True)
            payload = json.loads(body) if body else {}
            level = str(payload.get("level", "INFO")).upper()
            if level not in _VALID_LEVELS:
                level = "INFO"
            data = str(payload.get("data", ""))[:4096]
            _publish_log_event(level, data)
        except Exception:
            _logger.debug("LogController: kon log niet doorsturen naar RabbitMQ", exc_info=True)
        return http.Response("{}", content_type="application/json", status=200)
