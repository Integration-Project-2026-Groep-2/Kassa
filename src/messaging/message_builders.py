import datetime
import xml.etree.ElementTree as ET
from pathlib import Path

"""Helpers om XML-berichten te bouwen uit de templates/ directory.

We gebruiken de standaardlib `xml.etree.ElementTree` en lezen het template
bestand. Het template kan een voorbeeld-timestamp bevatten; we vervangen
de waarde door de actuele timestamp.
"""


TEMPLATE_PATH = Path(__file__).resolve().parents[2] / 'templates' / 'Heartbeat.xml'


def _read_template_text(path: Path) -> str:
    text = path.read_text(encoding='utf-8')
    # Sommige templates bevatten een eerste commentregel met een #-prefix;
    # verwijder zulke lijnen zodat XML-parser niet faalt.
    lines = [l for l in text.splitlines() if not l.lstrip().startswith('#')]
    return '\n'.join(lines)


def build_heartbeat_xml(service_name: str = 'TeamKassa') -> str:
    """Lees het Heartbeat-template en return een XML-string met actuele timestamp.

    - `service_name` wordt in het template gezet indien aanwezig.
    - Retourneert een string (UTF-8) die klaar is om naar RabbitMQ te sturen.
    """
    raw = _read_template_text(TEMPLATE_PATH)
    root = ET.fromstring(raw)

    # Zorg ervoor dat elementen bestaan en vul waar nodig
    sn = root.find('serviceName')
    if sn is None:
        sn = ET.SubElement(root, 'serviceName')
    sn.text = service_name

    ts = root.find('timestamp')
    if ts is None:
        ts = ET.SubElement(root, 'timestamp')
    # Zorg dat de XML als string terugkomt (zonder XML-declaratie)
    return ET.tostring(root, encoding='unicode')
