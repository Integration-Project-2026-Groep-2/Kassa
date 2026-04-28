"""Tests for the heartbeat XML builder.

These tests intentionally avoid importing the XML schema validator so the
heartbeat publisher stays independent from unrelated schema parsing issues.
"""

import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from messaging.message_builders import build_heartbeat_xml


def test_build_heartbeat_xml_returns_expected_contract_fields():
    xml_string = build_heartbeat_xml()
    root = ET.fromstring(xml_string)

    assert root.tag == 'Heartbeat'
    assert root.findtext('serviceId') == 'KASSA'
    assert root.findtext('timestamp')