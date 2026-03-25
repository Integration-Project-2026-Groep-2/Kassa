from __future__ import annotations

from datetime import datetime
from typing import Any

from lxml import etree


def _iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()


def _to_xml_bytes(root: etree._Element) -> bytes:
    return etree.tostring(root, encoding="utf-8", xml_declaration=True)


def build_heartbeat_xml(service_id: str, timestamp: datetime) -> bytes:
    root = etree.Element("Heartbeat")
    etree.SubElement(root, "serviceId").text = service_id
    etree.SubElement(root, "timestamp").text = _iso(timestamp)
    return _to_xml_bytes(root)


def build_status_check_xml(
    service_id: str,
    timestamp: datetime,
    status: str,
    uptime: int,
    cpu: float,
    memory: float,
    disk: float,
) -> bytes:
    root = etree.Element("StatusCheck")
    etree.SubElement(root, "serviceId").text = service_id
    etree.SubElement(root, "timestamp").text = _iso(timestamp)
    etree.SubElement(root, "status").text = status
    etree.SubElement(root, "uptime").text = str(uptime)

    system_load = etree.SubElement(root, "systemLoad")
    etree.SubElement(system_load, "cpu").text = f"{cpu:.4f}"
    etree.SubElement(system_load, "memory").text = f"{memory:.4f}"
    etree.SubElement(system_load, "disk").text = f"{disk:.4f}"

    return _to_xml_bytes(root)


def build_person_lookup_request_xml(request_id: str, email: str) -> bytes:
    root = etree.Element("PersonLookupRequest")
    etree.SubElement(root, "requestId").text = request_id
    etree.SubElement(root, "email").text = email
    return _to_xml_bytes(root)


def build_payment_confirmed_xml(
    email: str,
    amount: float,
    paid_at: datetime,
    user_id: str | None = None,
    registration_id: str | None = None,
    currency: str = "EUR",
) -> bytes:
    root = etree.Element("PaymentConfirmed")

    if user_id:
        etree.SubElement(root, "userId").text = user_id

    etree.SubElement(root, "email").text = email

    if registration_id:
        etree.SubElement(root, "registrationId").text = registration_id

    etree.SubElement(root, "amount").text = f"{amount:.2f}"
    etree.SubElement(root, "currency").text = currency
    etree.SubElement(root, "paidAt").text = _iso(paid_at)

    return _to_xml_bytes(root)


def build_unpaid_request_xml(request_id: str) -> bytes:
    root = etree.Element("UnpaidRequest")
    etree.SubElement(root, "requestId").text = request_id
    return _to_xml_bytes(root)


def build_invoice_requested_xml(
    order_id: str,
    user_id: str,
    company_id: str,
    amount: float,
    ordered_at: datetime,
    items: list[dict[str, Any]],
    email: str | None = None,
    company_name: str | None = None,
    event_id: str | None = None,
    payment_reference: str | None = None,
    currency: str = "EUR",
) -> bytes:
    root = etree.Element("InvoiceRequested")
    etree.SubElement(root, "orderId").text = order_id
    etree.SubElement(root, "userId").text = user_id
    etree.SubElement(root, "companyId").text = company_id
    etree.SubElement(root, "amount").text = f"{amount:.2f}"
    etree.SubElement(root, "currency").text = currency
    etree.SubElement(root, "orderedAt").text = _iso(ordered_at)

    items_el = etree.SubElement(root, "items")
    for item in items:
        item_el = etree.SubElement(items_el, "item")
        etree.SubElement(item_el, "productName").text = str(item["productName"])
        etree.SubElement(item_el, "quantity").text = str(item["quantity"])
        etree.SubElement(item_el, "unitPrice").text = f'{float(item["unitPrice"]):.2f}'

    if email:
        etree.SubElement(root, "email").text = email
    if company_name:
        etree.SubElement(root, "companyName").text = company_name
    if event_id:
        etree.SubElement(root, "eventId").text = event_id
    if payment_reference:
        etree.SubElement(root, "paymentReference").text = payment_reference

    return _to_xml_bytes(root)
