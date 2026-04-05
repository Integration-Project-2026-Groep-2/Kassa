# -*- coding: utf-8 -*-

"""
XML-validatie tegen het Kassa master schema (kassa-schema-v1.xsd).

Gebruik:
    from xml_validator import validate_xml

    ok, error = validate_xml(xml_string)
    if not ok:
        logger.error("Ongeldig XML-bericht: %s", error)

De validator wordt bij opstart geladen. Als het schema-bestand ontbreekt,
crasht de container direct (Docker healthcheck vangt dit op).
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / 'schema' / 'kassa-schema-v1.xsd'

try:
    from lxml import etree
    _schema_doc = etree.parse(str(SCHEMA_PATH))
    _schema = etree.XMLSchema(_schema_doc)
    logger.info("XML schema geladen: %s", SCHEMA_PATH)
except ImportError:
    # lxml niet geïnstalleerd — validatie uitgeschakeld, geen crash
    _schema = None
    logger.warning("lxml niet beschikbaar — XML-validatie uitgeschakeld")
except FileNotFoundError:
    raise FileNotFoundError(
        f"Verplicht schema-bestand niet gevonden: {SCHEMA_PATH}\n"
        "Zorg dat src/schema/kassa-schema-v1.xsd aanwezig is in de repo."
    )


def validate_xml(xml_string: str) -> tuple[bool, str | None]:
    """
    Valideer een XML-string tegen het Kassa master schema.

    Returns:
        (True, None)           als het bericht geldig is
        (False, error_message) als het bericht ongeldig is
    """
    if _schema is None:
        return True, None

    try:
        doc = etree.fromstring(xml_string.encode('utf-8'))
        _schema.assertValid(doc)
        return True, None
    except etree.DocumentInvalid as e:
        return False, str(e)
    except etree.XMLSyntaxError as e:
        return False, f"XML syntax fout: {e}"


def validate(xml_bytes: bytes) -> None:
    """
    Valideer XML-bytes tegen het Kassa master schema.
    Zelfde contract als de andere teams (CRM, Facturatie, ...):
    raises ValueError bij een ongeldig bericht.

    Gebruik dit in async code (heartbeat, status, sender).
    Gebruik validate_xml() als je een (bool, str) tuple nodig hebt.
    """
    if _schema is None:
        return

    try:
        doc = etree.fromstring(xml_bytes)
        _schema.assertValid(doc)
    except etree.DocumentInvalid as e:
        raise ValueError(f"Ongeldig XML-bericht: {e}") from e
    except etree.XMLSyntaxError as e:
        raise ValueError(f"XML syntax fout: {e}") from e
