# -*- coding: utf-8 -*-
"""
CheckIn consumer — IoT scanner → Kassa.

Ontvangt <CheckIn> XML-berichten van de fysieke IoT QR-scanner via RabbitMQ.
Het <id>-veld bevat de CRM UUID (user_id_custom) van de gebruiker die
zijn QR-code heeft getoond.

De consumer:
1. Valideert het bericht tegen check-in.xsd
2. Zoekt de partner op in Odoo via user_id_custom
3. Logt de check-in met naam en tijdstip

POS-selectie verloopt via de BadgeScanner (USB/BT) of QrScannerButton (camera).
"""

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from lxml import etree

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "contracts" / "check-in.xsd"

# Laad het schema éénmalig bij import — geen crash als bestand ontbreekt
try:
    _schema_doc = etree.parse(str(_SCHEMA_PATH))
    _check_in_schema = etree.XMLSchema(_schema_doc)
    logger.info("CheckIn XSD schema geladen: %s", _SCHEMA_PATH)
except FileNotFoundError:
    _check_in_schema = None
    logger.warning(
        "check-in.xsd niet gevonden (%s) — XSD-validatie uitgeschakeld voor CheckIn",
        _SCHEMA_PATH,
    )
except Exception as exc:
    _check_in_schema = None
    logger.warning("CheckIn schema kon niet geladen worden: %s", exc)


def _validate_check_in(xml_string: str) -> tuple[bool, Optional[str]]:
    """Valideer een CheckIn XML-string tegen check-in.xsd."""
    if _check_in_schema is None:
        return True, None
    try:
        doc = etree.fromstring(xml_string.encode("utf-8"))
        _check_in_schema.assertValid(doc)
        return True, None
    except etree.DocumentInvalid as exc:
        return False, str(exc)
    except etree.XMLSyntaxError as exc:
        return False, f"XML syntax fout: {exc}"


class CheckInConsumer:
    """
    Verwerkt inkomende CheckIn-berichten van de IoT QR-scanner.

    Verwacht een OdooUserRepository zodat de partner opgezocht kan worden
    zonder extra Odoo-verbinding aan te maken.
    """

    def __init__(self, odoo_user_repo):
        self.odoo_user_repo = odoo_user_repo

    def process(self, xml_payload: str) -> bool:
        """
        Verwerk een CheckIn XML-bericht.

        Args:
            xml_payload: UTF-8 gedecodeerde XML-string

        Returns:
            True bij succesvolle verwerking, False bij fout
        """
        ok, error = _validate_check_in(xml_payload)
        if not ok:
            logger.error("CheckIn: ongeldig XML-bericht: %s", error)
            return False

        try:
            root = ET.fromstring(xml_payload)
        except ET.ParseError as exc:
            logger.error("CheckIn: XML kon niet geparsed worden: %s", exc)
            return False

        user_id = (root.findtext("id") or "").strip()
        timestamp = (root.findtext("timestamp") or "").strip()

        if not user_id:
            logger.error("CheckIn: verplicht veld <id> ontbreekt")
            return False

        logger.info("CheckIn ontvangen [id=%s timestamp=%s]", user_id, timestamp)

        # Partner opzoeken in Odoo via CRM UUID (user_id_custom)
        try:
            partner = self.odoo_user_repo.get_user_by_user_id(user_id)
        except Exception as exc:
            logger.error("CheckIn: fout bij opzoeken partner [id=%s]: %s", user_id, exc)
            return False

        if partner:
            name = partner.get("name", "onbekend")
            badge = partner.get("badge_code", "")
            logger.info(
                "CheckIn verwerkt — partner gevonden [id=%s name=%s badge=%s timestamp=%s]",
                user_id, name, badge, timestamp,
            )
        else:
            logger.warning(
                "CheckIn: geen partner gevonden voor CRM-id=%s (timestamp=%s) "
                "— badge nog niet gesynchroniseerd?",
                user_id, timestamp,
            )

        return True
