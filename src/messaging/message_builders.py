import datetime
import xml.etree.ElementTree as ET
from pathlib import Path

"""
Helpers om XML-berichten te bouwen voor RabbitMQ.
Bevat builders voor: Heartbeat, ConsumptionOrder en PaymentCompleted.
"""

TEMPLATE_PATH = Path(__file__).resolve().parents[2] / 'templates' / 'Heartbeat.xml'


def _read_template_text(path: Path) -> str:
    text = path.read_text(encoding='utf-8')
    # Verwijder commentaarregels zodat de XML-parser niet faalt
    lines = [l for l in text.splitlines() if not l.lstrip().startswith('#')]
    return '\n'.join(lines)


def _now_iso() -> str:
    """Geeft de huidige UTC-tijd terug in ISO 8601 formaat (2026-03-29T12:00:00Z)."""
    return datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')


# ── Heartbeat ──────────────────────────────────────────────────────────────────

def build_heartbeat_xml(service_name: str = 'TeamKassa') -> str:
    """Bouw een Heartbeat XML-bericht met de actuele timestamp."""
    raw = _read_template_text(TEMPLATE_PATH)
    root = ET.fromstring(raw)

    sn = root.find('serviceName')
    if sn is None:
        sn = ET.SubElement(root, 'serviceName')
    sn.text = service_name

    ts = root.find('timestamp')
    if ts is None:
        ts = ET.SubElement(root, 'timestamp')
    ts.text = _now_iso()  # Was buggy: timestamp werd nooit ingevuld

    return ET.tostring(root, encoding='unicode')


# ── ConsumptionOrder ───────────────────────────────────────────────────────────

def build_consumption_order_xml(order_data: dict) -> str:
    """
    Bouw een ConsumptionOrder XML-bericht vanuit een order_data dict.
    Verwachte sleutels: orderId, userId, items[], totalAmount, paymentType, timestamp.
    """
    root = ET.Element('ConsumptionOrder')

    ET.SubElement(root, 'orderId').text = str(order_data.get('orderId', ''))
    ET.SubElement(root, 'userId').text = str(order_data.get('userId', ''))

    items_el = ET.SubElement(root, 'items')
    for item in order_data.get('items', []):
        item_el = ET.SubElement(items_el, 'item')
        ET.SubElement(item_el, 'productName').text = str(item.get('productName', ''))
        ET.SubElement(item_el, 'quantity').text = str(item.get('quantity', ''))
        ET.SubElement(item_el, 'price').text = str(item.get('price', ''))

    ET.SubElement(root, 'totalAmount').text = str(order_data.get('totalAmount', ''))
    ET.SubElement(root, 'paymentType').text = str(order_data.get('paymentType', ''))
    # Gebruik de timestamp van de order, of val terug op huidige tijd
    ET.SubElement(root, 'timestamp').text = str(order_data.get('timestamp') or _now_iso())

    return ET.tostring(root, encoding='unicode')


# ── PaymentCompleted ───────────────────────────────────────────────────────────

def build_payment_completed_xml(payment_data: dict) -> str:
    """
    Bouw een PaymentCompleted XML-bericht vanuit een payment_data dict.
    Verwachte sleutels: paymentId, orderId, userId, paymentMethod, amount, timestamp.
    """
    root = ET.Element('PaymentCompleted')

    ET.SubElement(root, 'paymentId').text = str(payment_data.get('paymentId', ''))
    ET.SubElement(root, 'orderId').text = str(payment_data.get('orderId', ''))
    ET.SubElement(root, 'userId').text = str(payment_data.get('userId', ''))
    ET.SubElement(root, 'paymentMethod').text = str(payment_data.get('paymentMethod', ''))
    ET.SubElement(root, 'amount').text = str(payment_data.get('amount', ''))
    ET.SubElement(root, 'timestamp').text = str(payment_data.get('timestamp') or _now_iso())

    return ET.tostring(root, encoding='unicode')
