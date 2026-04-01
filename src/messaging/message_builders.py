import datetime
import xml.etree.ElementTree as ET
from pathlib import Path

"""
Helpers om XML-berichten te bouwen voor RabbitMQ.
Bevat builders voor: Heartbeat (Contract 7), PaymentConfirmed (Contract 16),
InvoiceRequested (Contract K-01).
"""

TEMPLATE_PATH = Path(__file__).resolve().parents[2] / 'templates' / 'Heartbeat.xml'


def _read_template_text(path: Path) -> str:
    text = path.read_text(encoding='utf-8')
    return '\n'.join(l for l in text.splitlines() if not l.lstrip().startswith('#'))


def _now_iso() -> str:
    """Geeft de huidige UTC-tijd terug in ISO 8601 formaat (2026-03-29T12:00:00Z)."""
    return datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')


# ── Contract 7 — Heartbeat ─────────────────────────────────────────────────────

def build_heartbeat_xml() -> str:
    """
    Bouw een Heartbeat XML-bericht conform Contract 7.
    Verplichte velden: serviceId (KASSA), timestamp.
    Geen extra velden toegestaan.
    """
    raw = _read_template_text(TEMPLATE_PATH)
    root = ET.fromstring(raw)

    si = root.find('serviceId')
    if si is None:
        si = ET.SubElement(root, 'serviceId')
    si.text = 'KASSA'

    ts = root.find('timestamp')
    if ts is None:
        ts = ET.SubElement(root, 'timestamp')
    ts.text = _now_iso()

    return ET.tostring(root, encoding='unicode')


# ── Contract 16 — PaymentConfirmed ────────────────────────────────────────────

def build_payment_confirmed_xml(payment_data: dict) -> str:
    """
    Bouw een PaymentConfirmed XML-bericht conform Contract 16 (Kassa → CRM).

    Verplichte velden: email, amount, currency, paidAt
    Optionele velden: userId, registrationId
    """
    root = ET.Element('PaymentConfirmed')

    if payment_data.get('userId'):
        ET.SubElement(root, 'userId').text = str(payment_data['userId'])

    ET.SubElement(root, 'email').text = str(payment_data.get('email', ''))

    if payment_data.get('registrationId'):
        ET.SubElement(root, 'registrationId').text = str(payment_data['registrationId'])

    ET.SubElement(root, 'amount').text = str(payment_data.get('amount', '0'))
    ET.SubElement(root, 'currency').text = 'EUR'
    ET.SubElement(root, 'paidAt').text = str(payment_data.get('paidAt') or _now_iso())

    return ET.tostring(root, encoding='unicode')


# ── Contract K-01 — InvoiceRequested ──────────────────────────────────────────

def build_invoice_requested_xml(invoice_data: dict) -> str:
    """
    Bouw een InvoiceRequested XML-bericht conform Contract K-01 (Kassa → Facturatie).
    Alleen bij paymentType=Invoice en klant gelinkt aan een bedrijf.

    Verplichte velden: orderId, userId, companyId, amount, currency, orderedAt, items
    Optionele velden: email, companyName, eventId, paymentReference
    Items: productName, quantity, unitPrice
    """
    root = ET.Element('InvoiceRequested')

    ET.SubElement(root, 'orderId').text = str(invoice_data.get('orderId', ''))
    ET.SubElement(root, 'userId').text = str(invoice_data.get('userId', ''))
    ET.SubElement(root, 'companyId').text = str(invoice_data.get('companyId', ''))
    ET.SubElement(root, 'amount').text = str(invoice_data.get('amount', '0'))
    ET.SubElement(root, 'currency').text = 'EUR'
    ET.SubElement(root, 'orderedAt').text = str(invoice_data.get('orderedAt') or _now_iso())

    items_el = ET.SubElement(root, 'items')
    for item in invoice_data.get('items', []):
        item_el = ET.SubElement(items_el, 'item')
        ET.SubElement(item_el, 'productName').text = str(item.get('productName', ''))
        ET.SubElement(item_el, 'quantity').text = str(item.get('quantity', ''))
        ET.SubElement(item_el, 'unitPrice').text = str(item.get('unitPrice', ''))

    if invoice_data.get('email'):
        ET.SubElement(root, 'email').text = str(invoice_data['email'])
    if invoice_data.get('companyName'):
        ET.SubElement(root, 'companyName').text = str(invoice_data['companyName'])
    if invoice_data.get('eventId'):
        ET.SubElement(root, 'eventId').text = str(invoice_data['eventId'])
    if invoice_data.get('paymentReference'):
        ET.SubElement(root, 'paymentReference').text = str(invoice_data['paymentReference'])

    return ET.tostring(root, encoding='unicode')
