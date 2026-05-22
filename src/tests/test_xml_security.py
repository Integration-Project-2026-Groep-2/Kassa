import unittest

from xml_validator import validate_xml


class TestXMLSecurity(unittest.TestCase):
    def test_xxe_external_entity_rejected(self):
        """Ensure XML with external entities (XXE) is rejected by the validator."""
        malicious = '''<?xml version="1.0"?>
        <!DOCTYPE root [
          <!ENTITY xxe SYSTEM "file:///c:/windows/win.ini">
        ]>
        <root>&xxe;</root>
        '''

        ok, error = validate_xml(malicious)
        self.assertFalse(ok)
        self.assertIsNotNone(error)


if __name__ == '__main__':
    unittest.main()
