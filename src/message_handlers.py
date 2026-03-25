from __future__ import annotations

import logging
from typing import Optional

from lxml import etree

from odoo_client import OdooClient


def _text(element: etree._Element, name: str, default: str | None = None) -> str | None:
    found = element.find(name)
    if found is None or found.text is None:
        return default
    return found.text


def _bool(element: etree._Element, name: str, default: bool = False) -> bool:
    value = _text(element, name)
    if value is None:
        return default
    return value.strip().lower() == "true"


async def handle_warning(
    root: etree._Element,
    _odoo_client: OdooClient,
    logger: logging.Logger,
) -> None:
    service_id = _text(root, "serviceId", "UNKNOWN")
    message = _text(root, "message", "")
    warning_type = _text(root, "type", "unknown")
    logger.warning("Controlroom warning received - service=%s type=%s msg=%s", service_id, warning_type, message)


async def handle_person_lookup_response(
    root: etree._Element,
    _odoo_client: OdooClient,
    logger: logging.Logger,
) -> None:
    request_id = _text(root, "requestId", "")
    found = _bool(root, "found")
    linked_to_company = _bool(root, "linkedToCompany")
    logger.info(
        "Person lookup response received - requestId=%s found=%s linkedToCompany=%s",
        request_id,
        found,
        linked_to_company,
    )


async def handle_user_confirmed(
    root: etree._Element,
    odoo_client: OdooClient,
    logger: logging.Logger,
) -> None:
    await odoo_client.upsert_partner(
        crm_id=_text(root, "id", "") or "",
        email=_text(root, "email", "") or "",
        first_name=_text(root, "firstName", "") or "",
        last_name=_text(root, "lastName", "") or "",
        role=_text(root, "role", "") or "",
        is_active=_bool(root, "isActive", True),
        phone=_text(root, "phone"),
        badge_code=_text(root, "badgeCode"),
        company_crm_id=_text(root, "companyId"),
    )
    logger.info("Handled UserConfirmed message.")


async def handle_company_confirmed(
    root: etree._Element,
    odoo_client: OdooClient,
    logger: logging.Logger,
) -> None:
    await odoo_client.upsert_company(
        crm_id=_text(root, "id", "") or "",
        vat_number=_text(root, "vatNumber", "") or "",
        name=_text(root, "name", "") or "",
        email=_text(root, "email", "") or "",
        is_active=_bool(root, "isActive", True),
    )
    logger.info("Handled CompanyConfirmed message.")


async def handle_unpaid_response(
    root: etree._Element,
    _odoo_client: OdooClient,
    logger: logging.Logger,
) -> None:
    persons = root.find("persons")
    count = 0 if persons is None else len(persons.findall("person"))
    request_id = _text(root, "requestId", "")
    logger.info("Handled UnpaidResponse - requestId=%s count=%s", request_id, count)


async def handle_user_updated(
    root: etree._Element,
    odoo_client: OdooClient,
    logger: logging.Logger,
) -> None:
    await odoo_client.upsert_partner(
        crm_id=_text(root, "id", "") or "",
        email=_text(root, "email", "") or "",
        first_name=_text(root, "firstName", "") or "",
        last_name=_text(root, "lastName", "") or "",
        role=_text(root, "role", "") or "",
        is_active=_bool(root, "isActive", True),
        phone=_text(root, "phone"),
        badge_code=_text(root, "badgeCode"),
        company_crm_id=_text(root, "companyId"),
        street=_text(root, "street"),
        house_number=_text(root, "houseNumber"),
        postal_code=_text(root, "postalCode"),
        city=_text(root, "city"),
        country=_text(root, "country"),
    )
    logger.info("Handled UserUpdated message.")


async def handle_company_updated(
    root: etree._Element,
    odoo_client: OdooClient,
    logger: logging.Logger,
) -> None:
    await odoo_client.upsert_company(
        crm_id=_text(root, "id", "") or "",
        vat_number=_text(root, "vatNumber", "") or "",
        name=_text(root, "name", "") or "",
        email=_text(root, "email", "") or "",
        is_active=_bool(root, "isActive", True),
        phone=_text(root, "phone"),
        street=_text(root, "street"),
        house_number=_text(root, "houseNumber"),
        postal_code=_text(root, "postalCode"),
        city=_text(root, "city"),
        country=_text(root, "country"),
    )
    logger.info("Handled CompanyUpdated message.")


async def handle_user_deactivated(
    root: etree._Element,
    odoo_client: OdooClient,
    logger: logging.Logger,
) -> None:
    await odoo_client.deactivate_partner_by_crm_id_or_email(
        crm_id=_text(root, "id", "") or "",
        email=_text(root, "email", "") or "",
    )
    logger.info("Handled UserDeactivated message.")


async def handle_company_deactivated(
    root: etree._Element,
    odoo_client: OdooClient,
    logger: logging.Logger,
) -> None:
    await odoo_client.deactivate_company_by_crm_id(_text(root, "id", "") or "")
    logger.info("Handled CompanyDeactivated message.")


HANDLER_MAP = {
    "Warning": handle_warning,
    "PersonLookupResponse": handle_person_lookup_response,
    "UserConfirmed": handle_user_confirmed,
    "CompanyConfirmed": handle_company_confirmed,
    "UnpaidResponse": handle_unpaid_response,
    "UserUpdated": handle_user_updated,
    "CompanyUpdated": handle_company_updated,
    "UserDeactivated": handle_user_deactivated,
    "CompanyDeactivated": handle_company_deactivated,
}


async def dispatch_message(
    xml_bytes: bytes,
    odoo_client: OdooClient,
    logger: logging.Logger,
) -> None:
    root = etree.fromstring(xml_bytes)
    handler = HANDLER_MAP.get(root.tag)

    if handler is None:
        logger.warning("No handler found for XML root '%s'.", root.tag)
        return

    await handler(root, odoo_client, logger)
