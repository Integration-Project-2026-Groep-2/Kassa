import datetime
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional, Tuple

from xml_validator import validate_xml

"""
Helpers om XML-berichten te bouwen voor RabbitMQ.
Bevat builders voor: Heartbeat (Contract 7), PaymentConfirmed (Contract 16),
InvoiceRequested (Contract K-01), User (CRUD operations).
"""

TEMPLATE_PATH = Path(__file__).resolve().parents[2] / 'templates' / 'Heartbeat.xml'

logger = logging.getLogger(__name__)


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


# ── User CRUD Operations ──────────────────────────────────────────────────────

def build_user_xml(user_data: Dict) -> str:
    """
    Bouw een User XML-bericht conform het schema.
    
    Verplichte velden: userId, firstName, lastName, email, badgeCode, role
    Optionele velden: companyId, createdAt, updatedAt
    
    Args:
        user_data: Dictionary with user information (lowerCamelCase)
    
    Returns:
        XML string representation of the user
    """
    root = ET.Element('User')

    ET.SubElement(root, 'userId').text = str(user_data.get('userId', ''))
    ET.SubElement(root, 'firstName').text = str(user_data.get('firstName', ''))
    ET.SubElement(root, 'lastName').text = str(user_data.get('lastName', ''))
    ET.SubElement(root, 'email').text = str(user_data.get('email', ''))
    
    if user_data.get('companyId'):
        ET.SubElement(root, 'companyId').text = str(user_data['companyId'])
    
    ET.SubElement(root, 'badgeCode').text = str(user_data.get('badgeCode', ''))
    ET.SubElement(root, 'role').text = str(user_data.get('role', ''))
    
    if user_data.get('createdAt'):
        ET.SubElement(root, 'createdAt').text = str(user_data['createdAt'])
    if user_data.get('updatedAt'):
        ET.SubElement(root, 'updatedAt').text = str(user_data['updatedAt'])

    xml_string = ET.tostring(root, encoding='unicode')
    valid, error = validate_xml(xml_string)
    if not valid:
        logger.error("Invalid User XML generated: %s", error)
        raise ValueError(f"Invalid User XML generated: {error}")

    return xml_string


def parse_user_xml(xml_string: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
    """
    Parse a User XML string into a dictionary.
    
    Args:
        xml_string: XML string containing user data
    
    Returns:
        (True, None, user_dict) on success
        (False, error_message, None) on failure
    """
    try:
        root = ET.fromstring(xml_string)
        
        # Extract required fields
        user_data = {
            'userId': root.findtext('userId', '').strip(),
            'firstName': root.findtext('firstName', '').strip(),
            'lastName': root.findtext('lastName', '').strip(),
            'email': root.findtext('email', '').strip(),
            'badgeCode': root.findtext('badgeCode', '').strip(),
            'role': root.findtext('role', '').strip(),
        }
        
        # Extract optional fields
        companyId = root.findtext('companyId', '').strip()
        if companyId:
            user_data['companyId'] = companyId
        
        createdAt = root.findtext('createdAt', '').strip()
        if createdAt:
            user_data['createdAt'] = createdAt
        
        updatedAt = root.findtext('updatedAt', '').strip()
        if updatedAt:
            user_data['updatedAt'] = updatedAt
        
        return True, None, user_data
    
    except ET.ParseError as e:
        error = f"Failed to parse User XML: {str(e)}"
        return False, error, None
    except Exception as e:
        error = f"Unexpected error parsing User XML: {str(e)}"
        return False, error, None


def build_user_created_message(user_data: Dict) -> str:
    """
    Build a UserCreated event message for RabbitMQ.
    
    Args:
        user_data: Dict with user information
    
    Returns:
        XML string for UserCreated message
    """
    return build_user_xml(user_data)


def build_user_updated_message(user_data: Dict) -> str:
    """
    Build a UserUpdated event message for RabbitMQ.
    
    Args:
        user_data: Dict with updated user information
    
    Returns:
        XML string for UserUpdated message
    """
    return build_user_xml(user_data)


def build_user_deleted_message(user_id: str) -> str:
    """
    Build a UserDeleted event message for RabbitMQ.
    
    Args:
        user_id: UUID of the deleted user
    
    Returns:
        XML string for UserDeleted message
    """
    root = ET.Element('UserDeleted')
    ET.SubElement(root, 'userId').text = str(user_id)
    ET.SubElement(root, 'deletedAt').text = _now_iso()
    
    return ET.tostring(root, encoding='unicode')


# ── BatchClosed — Afsluitknop (Closing Button) ────────────────────────────────

def build_batch_closed_xml(batch_data: dict) -> str:
    """
    Bouw een BatchClosed XML-bericht conform het kassa.closed contract.
    
    Dit bericht wordt gegenereerd wanneer de POS-afsluitknop wordt ingedrukt.
    Het bevat alle transacties van die dag voor geïdentificeerde klanten met 
    paymentType=Invoice.
    
    batch_data moet bevatten:
    {
        'batchId': str (UUID),
        'closedAt': str (ISO8601, optional - default now),
        'currency': str (optional - default 'EUR'),
        'users': [
            {
                'userId': str (UUID),
                'items': [
                    {
                        'productName': str,
                        'quantity': int,
                        'unitPrice': float,
                        'totalPrice': float
                    },
                    ...
                ],
                'totalAmount': float
            },
            ...
        ],
        'totalOrders': int,
        'totalAmount': float,
        'orderIds': [str (UUID), ...]
    }
    
    Returns:
        XML string representation of the batch
    """
    root = ET.Element('BatchClosed')
    
    # Required: batchId
    ET.SubElement(root, 'batchId').text = str(batch_data.get('batchId', ''))
    
    # Required: closedAt
    closed_at = batch_data.get('closedAt') or _now_iso()
    ET.SubElement(root, 'closedAt').text = str(closed_at)
    
    # Required: currency
    ET.SubElement(root, 'currency').text = batch_data.get('currency', 'EUR')
    
    # Optional: users with their items
    if batch_data.get('users'):
        users_el = ET.SubElement(root, 'users')
        for user in batch_data['users']:
            user_el = ET.SubElement(users_el, 'user')
            
            ET.SubElement(user_el, 'userId').text = str(user.get('userId', ''))
            
            # Items grouped by user
            if user.get('items'):
                items_el = ET.SubElement(user_el, 'items')
                for item in user['items']:
                    item_el = ET.SubElement(items_el, 'item')
                    ET.SubElement(item_el, 'productName').text = str(item.get('productName', ''))
                    ET.SubElement(item_el, 'quantity').text = str(item.get('quantity', '0'))
                    ET.SubElement(item_el, 'unitPrice').text = f"{float(item.get('unitPrice', 0)):.2f}"
                    ET.SubElement(item_el, 'totalPrice').text = f"{float(item.get('totalPrice', 0)):.2f}"
            
            ET.SubElement(user_el, 'totalAmount').text = f"{float(user.get('totalAmount', 0)):.2f}"
    
    # Required: summary
    summary_el = ET.SubElement(root, 'summary')
    ET.SubElement(summary_el, 'totalOrders').text = str(batch_data.get('totalOrders', 0))
    ET.SubElement(summary_el, 'totalAmount').text = f"{float(batch_data.get('totalAmount', 0)):.2f}"
    
    if batch_data.get('orderIds'):
        order_ids_el = ET.SubElement(summary_el, 'orderIds')
        for order_id in batch_data['orderIds']:
            ET.SubElement(order_ids_el, 'orderId').text = str(order_id)
    
    return ET.tostring(root, encoding='unicode')
