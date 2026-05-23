"""
Tests voor XSD-validatie van CheckIn-berichten (IoT QR-scanner → Kassa).
Valideert de check-in.xsd schema direct via de interne helperfunctie.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from messaging.check_in_consumer import _validate_check_in


# ── Helpers ────────────────────────────────────────────────────────────────────

def valid(xml: str) -> None:
    ok, error = _validate_check_in(xml)
    assert ok, f"Verwacht geldig, maar fout: {error}"


def invalid(xml: str) -> None:
    ok, error = _validate_check_in(xml)
    assert not ok, "Verwacht ongeldig, maar werd geaccepteerd"


# ── Geldige berichten ──────────────────────────────────────────────────────────

def test_check_in_geldig_met_timezone():
    valid("""<?xml version='1.0' encoding='UTF-8'?>
    <CheckIn>
        <id>550e8400-e29b-41d4-a716-446655440000</id>
        <timestamp>2026-05-23T14:30:00+02:00</timestamp>
    </CheckIn>""")


def test_check_in_geldig_utc():
    valid("""<CheckIn>
        <id>abc-123</id>
        <timestamp>2026-05-23T12:30:00Z</timestamp>
    </CheckIn>""")


def test_check_in_geldig_badge_als_id():
    valid("""<CheckIn>
        <id>TEST001</id>
        <timestamp>2026-01-01T00:00:00Z</timestamp>
    </CheckIn>""")


# ── Ontbrekende verplichte velden ──────────────────────────────────────────────

def test_check_in_ongeldig_zonder_id():
    invalid("""<CheckIn>
        <timestamp>2026-05-23T14:30:00Z</timestamp>
    </CheckIn>""")


def test_check_in_ongeldig_zonder_timestamp():
    invalid("""<CheckIn>
        <id>550e8400-e29b-41d4-a716-446655440000</id>
    </CheckIn>""")


def test_check_in_ongeldig_leeg():
    invalid("<CheckIn/>")


# ── Foutief formaat ────────────────────────────────────────────────────────────

def test_check_in_ongeldig_timestamp_geen_iso8601():
    invalid("""<CheckIn>
        <id>some-id</id>
        <timestamp>23-05-2026 14:30</timestamp>
    </CheckIn>""")


def test_check_in_ongeldig_timestamp_alleen_datum():
    invalid("""<CheckIn>
        <id>some-id</id>
        <timestamp>2026-05-23</timestamp>
    </CheckIn>""")


# ── Verkeerde root ─────────────────────────────────────────────────────────────

def test_check_in_ongeldig_verkeerde_root():
    invalid("""<Badge>
        <id>some-id</id>
        <timestamp>2026-05-23T14:30:00Z</timestamp>
    </Badge>""")


def test_check_in_ongeldig_kapotte_xml():
    ok, error = _validate_check_in("<CheckIn><id>test</WRONG>")
    assert not ok
    assert error is not None
