from __future__ import annotations

from pathlib import Path

from lxml import etree


class XMLValidator:
    def __init__(self, schema_path: str) -> None:
        self.schema_path = schema_path
        self.schema = self._load_schema(schema_path)

    @staticmethod
    def _load_schema(schema_path: str) -> etree.XMLSchema:
        path = Path(schema_path)
        if not path.exists():
            raise FileNotFoundError(f"XSD schema not found: {schema_path}")

        schema_doc = etree.parse(str(path))
        return etree.XMLSchema(schema_doc)

    def validate(self, xml_bytes: bytes) -> None:
        try:
            doc = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError as exc:
            raise ValueError(f"Invalid XML syntax: {exc}") from exc

        if not self.schema.validate(doc):
            raise ValueError(str(self.schema.error_log))
