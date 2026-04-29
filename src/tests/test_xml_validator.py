"""
Tests voor XSD-validatie van alle Kassa-contracten.
Elk contract krijgt een geldige en een ongeldige variant.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from xml_validator import validate_xml, validate_kassa


# ── Helpers ────────────────────────────────────────────────────────────────────

def valid(xml: str) -> None:
    ok, error = validate_xml(xml)
    assert ok, f"Verwacht geldig, maar fout: {error}"


def invalid(xml: str) -> None:
    ok, error = validate_xml(xml)
    assert not ok, "Verwacht ongeldig, maar werd geaccepteerd"


def valid_kassa(xml: str) -> None:
    ok, error = validate_kassa(xml)
    assert ok, f"Verwacht geldig (kassa-user.xsd), maar fout: {error}"


def invalid_kassa(xml: str) -> None:
    ok, error = validate_kassa(xml)
    assert not ok, "Verwacht ongeldig (kassa-user.xsd), maar werd geaccepteerd"


# ── Contract 7 — Heartbeat ─────────────────────────────────────────────────────

def test_heartbeat_valid():
    valid("""<Heartbeat>
        <serviceId>KASSA</serviceId>
        <timestamp>2026-04-18T10:00:00Z</timestamp>
    </Heartbeat>""")


def test_heartbeat_missing_timestamp():
    invalid("""<Heartbeat>
        <serviceId>KASSA</serviceId>
    </Heartbeat>""")


def test_heartbeat_wrong_service_id():
    invalid("""<Heartbeat>
        <serviceId>CRM</serviceId>
        <timestamp>2026-04-18T10:00:00Z</timestamp>
    </Heartbeat>""")


# ── Contract 8 — StatusCheck ───────────────────────────────────────────────────

def test_statuscheck_valid():
    valid("""<StatusCheck>
        <serviceId>KASSA</serviceId>
        <timestamp>2026-04-18T10:00:00Z</timestamp>
        <status>healthy</status>
        <uptime>3600</uptime>
        <systemLoad>
            <cpu>0.10</cpu>
            <memory>0.40</memory>
            <disk>0.20</disk>
        </systemLoad>
    </StatusCheck>""")


def test_statuscheck_degraded_valid():
    valid("""<StatusCheck>
        <serviceId>KASSA</serviceId>
        <timestamp>2026-04-18T10:00:00Z</timestamp>
        <status>degraded</status>
        <uptime>0</uptime>
        <systemLoad>
            <cpu>0.95</cpu>
            <memory>0.95</memory>
            <disk>0.50</disk>
        </systemLoad>
    </StatusCheck>""")


def test_statuscheck_invalid_status():
    invalid("""<StatusCheck>
        <serviceId>KASSA</serviceId>
        <timestamp>2026-04-18T10:00:00Z</timestamp>
        <status>ok</status>
        <uptime>0</uptime>
        <systemLoad>
            <cpu>0.10</cpu>
            <memory>0.10</memory>
            <disk>0.10</disk>
        </systemLoad>
    </StatusCheck>""")


def test_statuscheck_cpu_out_of_range():
    invalid("""<StatusCheck>
        <serviceId>KASSA</serviceId>
        <timestamp>2026-04-18T10:00:00Z</timestamp>
        <status>healthy</status>
        <uptime>0</uptime>
        <systemLoad>
            <cpu>1.50</cpu>
            <memory>0.10</memory>
            <disk>0.10</disk>
        </systemLoad>
    </StatusCheck>""")


# ── Contract 9 — Warning ───────────────────────────────────────────────────────

def test_warning_valid():
    valid("""<Warning>
        <serviceId>KASSA</serviceId>
        <message>Heartbeat gemist</message>
        <type>heartbeat</type>
    </Warning>""")


def test_warning_invalid_type():
    invalid("""<Warning>
        <serviceId>KASSA</serviceId>
        <message>Onbekende fout</message>
        <type>unknown_type</type>
    </Warning>""")


# ── Contract 10a — PersonLookupRequest ────────────────────────────────────────

def test_person_lookup_request_valid():
    valid("""<PersonLookupRequest>
        <requestId>abc-123</requestId>
        <email>test@example.com</email>
    </PersonLookupRequest>""")


def test_person_lookup_request_invalid_email():
    invalid("""<PersonLookupRequest>
        <requestId>abc-123</requestId>
        <email>geen-email</email>
    </PersonLookupRequest>""")


def test_person_lookup_request_missing_email():
    invalid("""<PersonLookupRequest>
        <requestId>abc-123</requestId>
    </PersonLookupRequest>""")


# ── Contract 10b — PersonLookupResponse ───────────────────────────────────────

def test_person_lookup_response_found():
    valid("""<PersonLookupResponse>
        <requestId>abc-123</requestId>
        <found>true</found>
        <linkedToCompany>false</linkedToCompany>
        <id>550e8400-e29b-4ed4-a716-446655440000</id>
    </PersonLookupResponse>""")


def test_person_lookup_response_not_found():
    valid("""<PersonLookupResponse>
        <requestId>abc-123</requestId>
        <found>false</found>
        <linkedToCompany>false</linkedToCompany>
    </PersonLookupResponse>""")


def test_person_lookup_response_missing_found():
    invalid("""<PersonLookupResponse>
        <requestId>abc-123</requestId>
        <linkedToCompany>false</linkedToCompany>
    </PersonLookupResponse>""")


# ── Contract 13 — UserConfirmed ────────────────────────────────────────────────

def test_user_confirmed_valid():
    valid("""<UserConfirmed>
        <id>550e8400-e29b-4ed4-a716-446655440000</id>
        <email>jan@example.com</email>
        <firstName>Jan</firstName>
        <lastName>Peeters</lastName>
        <role>VISITOR</role>
        <isActive>true</isActive>
        <gdprConsent>true</gdprConsent>
        <confirmedAt>2026-04-18T10:00:00Z</confirmedAt>
    </UserConfirmed>""")


def test_user_confirmed_invalid_role():
    invalid("""<UserConfirmed>
        <id>550e8400-e29b-4ed4-a716-446655440000</id>
        <email>jan@example.com</email>
        <firstName>Jan</firstName>
        <lastName>Peeters</lastName>
        <role>ONBEKEND</role>
        <isActive>true</isActive>
        <gdprConsent>true</gdprConsent>
        <confirmedAt>2026-04-18T10:00:00Z</confirmedAt>
    </UserConfirmed>""")


def test_user_confirmed_invalid_uuid():
    invalid("""<UserConfirmed>
        <id>geen-uuid</id>
        <email>jan@example.com</email>
        <firstName>Jan</firstName>
        <lastName>Peeters</lastName>
        <role>VISITOR</role>
        <isActive>true</isActive>
        <gdprConsent>true</gdprConsent>
        <confirmedAt>2026-04-18T10:00:00Z</confirmedAt>
    </UserConfirmed>""")


# ── Contract 14 — CompanyConfirmed ────────────────────────────────────────────

def test_company_confirmed_valid():
    valid("""<CompanyConfirmed>
        <id>550e8400-e29b-4ed4-a716-446655440000</id>
        <vatNumber>BE0123456789</vatNumber>
        <name>Bedrijf NV</name>
        <email>info@bedrijf.be</email>
        <isActive>true</isActive>
        <confirmedAt>2026-04-18T10:00:00Z</confirmedAt>
    </CompanyConfirmed>""")


def test_company_confirmed_invalid_vat():
    invalid("""<CompanyConfirmed>
        <id>550e8400-e29b-4ed4-a716-446655440000</id>
        <vatNumber>NL0123456789</vatNumber>
        <name>Bedrijf NV</name>
        <email>info@bedrijf.be</email>
        <isActive>true</isActive>
        <confirmedAt>2026-04-18T10:00:00Z</confirmedAt>
    </CompanyConfirmed>""")


# ── Contract 16 — PaymentConfirmed ────────────────────────────────────────────

def test_payment_confirmed_valid():
    valid("""<PaymentConfirmed>
        <email>klant@example.com</email>
        <amount>12.50</amount>
        <currency>EUR</currency>
        <paidAt>2026-04-18T10:00:00Z</paidAt>
    </PaymentConfirmed>""")


def test_payment_confirmed_negative_amount():
    invalid("""<PaymentConfirmed>
        <email>klant@example.com</email>
        <amount>-5.00</amount>
        <currency>EUR</currency>
        <paidAt>2026-04-18T10:00:00Z</paidAt>
    </PaymentConfirmed>""")


def test_payment_confirmed_wrong_currency():
    invalid("""<PaymentConfirmed>
        <email>klant@example.com</email>
        <amount>10.00</amount>
        <currency>USD</currency>
        <paidAt>2026-04-18T10:00:00Z</paidAt>
    </PaymentConfirmed>""")


# ── Contract 17a — UnpaidRequest ──────────────────────────────────────────────

def test_unpaid_request_valid():
    valid("""<UnpaidRequest>
        <requestId>req-001</requestId>
    </UnpaidRequest>""")


def test_unpaid_request_missing_request_id():
    invalid("""<UnpaidRequest/>""")


# ── Contract 17b — UnpaidResponse ─────────────────────────────────────────────

def test_unpaid_response_valid_empty():
    valid("""<UnpaidResponse>
        <requestId>req-001</requestId>
        <persons/>
    </UnpaidResponse>""")


def test_unpaid_response_with_persons():
    valid("""<UnpaidResponse>
        <requestId>req-001</requestId>
        <persons>
            <person>
                <id>550e8400-e29b-4ed4-a716-446655440000</id>
                <firstName>Jan</firstName>
                <lastName>Peeters</lastName>
                <email>jan@example.com</email>
                <linkedToCompany>false</linkedToCompany>
            </person>
        </persons>
    </UnpaidResponse>""")


# ── Contract 18 — UserUpdated ─────────────────────────────────────────────────

def test_user_updated_valid():
    valid("""<UserUpdated>
        <id>550e8400-e29b-4ed4-a716-446655440000</id>
        <email>jan@example.com</email>
        <firstName>Jan</firstName>
        <lastName>Peeters</lastName>
        <role>VISITOR</role>
        <isActive>true</isActive>
        <gdprConsent>true</gdprConsent>
        <updatedAt>2026-04-18T10:00:00Z</updatedAt>
    </UserUpdated>""")


# ── Contract 19 — CompanyUpdated ──────────────────────────────────────────────

def test_company_updated_valid():
    valid("""<CompanyUpdated>
        <id>550e8400-e29b-4ed4-a716-446655440000</id>
        <vatNumber>BE0123456789</vatNumber>
        <name>Bedrijf NV</name>
        <isActive>true</isActive>
        <updatedAt>2026-04-18T10:00:00Z</updatedAt>
    </CompanyUpdated>""")


def test_company_updated_invalid_country():
    invalid("""<CompanyUpdated>
        <id>550e8400-e29b-4ed4-a716-446655440000</id>
        <vatNumber>BE0123456789</vatNumber>
        <name>Bedrijf NV</name>
        <isActive>true</isActive>
        <updatedAt>2026-04-18T10:00:00Z</updatedAt>
        <country>belgie</country>
    </CompanyUpdated>""")


# ── Contract 22 — UserDeactivated ─────────────────────────────────────────────

def test_user_deactivated_valid():
    valid("""<UserDeactivated>
        <id>550e8400-e29b-4ed4-a716-446655440000</id>
        <email>jan@example.com</email>
        <deactivatedAt>2026-04-18T10:00:00Z</deactivatedAt>
    </UserDeactivated>""")


def test_user_deactivated_missing_email():
    invalid("""<UserDeactivated>
        <id>550e8400-e29b-4ed4-a716-446655440000</id>
        <deactivatedAt>2026-04-18T10:00:00Z</deactivatedAt>
    </UserDeactivated>""")


# ── Contract 23 — CompanyDeactivated ──────────────────────────────────────────

def test_company_deactivated_valid():
    valid("""<CompanyDeactivated>
        <id>550e8400-e29b-4ed4-a716-446655440000</id>
        <vatNumber>BE0123456789</vatNumber>
        <deactivatedAt>2026-04-18T10:00:00Z</deactivatedAt>
    </CompanyDeactivated>""")


# ── Contract K-01 — InvoiceRequested ──────────────────────────────────────────

def test_invoice_requested_valid():
    valid("""<InvoiceRequested>
        <orderId>order-001</orderId>
        <userId>550e8400-e29b-4ed4-a716-446655440000</userId>
        <companyId>550e8400-e29b-4ed4-a716-446655440001</companyId>
        <amount>49.99</amount>
        <currency>EUR</currency>
        <orderedAt>2026-04-18T10:00:00Z</orderedAt>
        <items>
            <item>
                <productName>Bier</productName>
                <quantity>2</quantity>
                <unitPrice>3.50</unitPrice>
            </item>
        </items>
    </InvoiceRequested>""")


def test_invoice_requested_no_items():
    invalid("""<InvoiceRequested>
        <orderId>order-001</orderId>
        <userId>550e8400-e29b-4ed4-a716-446655440000</userId>
        <companyId>550e8400-e29b-4ed4-a716-446655440001</companyId>
        <amount>49.99</amount>
        <currency>EUR</currency>
        <orderedAt>2026-04-18T10:00:00Z</orderedAt>
        <items/>
    </InvoiceRequested>""")


def test_invoice_requested_missing_company_id():
    invalid("""<InvoiceRequested>
        <orderId>order-001</orderId>
        <userId>550e8400-e29b-4ed4-a716-446655440000</userId>
        <amount>49.99</amount>
        <currency>EUR</currency>
        <orderedAt>2026-04-18T10:00:00Z</orderedAt>
        <items>
            <item>
                <productName>Bier</productName>
                <quantity>1</quantity>
                <unitPrice>3.50</unitPrice>
            </item>
        </items>
    </InvoiceRequested>""")


# ── Contract 36 — KassaUserCreated ────────────────────────────────────────────

def test_kassa_user_created_valid():
    valid_kassa("""<KassaUserCreated>
        <userId>550e8400-e29b-4ed4-a716-446655440000</userId>
        <firstName>Jan</firstName>
        <lastName>Peeters</lastName>
        <email>jan@example.com</email>
        <badgeCode>BADGE001</badgeCode>
        <role>VISITOR</role>
        <createdAt>2026-04-18T10:00:00Z</createdAt>
    </KassaUserCreated>""")


def test_kassa_user_created_with_company():
    valid_kassa("""<KassaUserCreated>
        <userId>550e8400-e29b-4ed4-a716-446655440000</userId>
        <firstName>Jan</firstName>
        <lastName>Peeters</lastName>
        <email>jan@example.com</email>
        <companyId>550e8400-e29b-4ed4-a716-446655440001</companyId>
        <badgeCode>BADGE001</badgeCode>
        <role>COMPANY_CONTACT</role>
        <createdAt>2026-04-18T10:00:00Z</createdAt>
    </KassaUserCreated>""")


def test_kassa_user_created_empty_badge_code():
    """badgeCode mag niet leeg zijn (NonEmptyStringType, PR #121)."""
    invalid_kassa("""<KassaUserCreated>
        <userId>550e8400-e29b-4ed4-a716-446655440000</userId>
        <firstName>Jan</firstName>
        <lastName>Peeters</lastName>
        <email>jan@example.com</email>
        <badgeCode></badgeCode>
        <role>VISITOR</role>
        <createdAt>2026-04-18T10:00:00Z</createdAt>
    </KassaUserCreated>""")


def test_kassa_user_created_invalid_role():
    invalid_kassa("""<KassaUserCreated>
        <userId>550e8400-e29b-4ed4-a716-446655440000</userId>
        <firstName>Jan</firstName>
        <lastName>Peeters</lastName>
        <email>jan@example.com</email>
        <badgeCode>BADGE001</badgeCode>
        <role>KLANT</role>
        <createdAt>2026-04-18T10:00:00Z</createdAt>
    </KassaUserCreated>""")


def test_kassa_user_created_missing_created_at():
    invalid_kassa("""<KassaUserCreated>
        <userId>550e8400-e29b-4ed4-a716-446655440000</userId>
        <firstName>Jan</firstName>
        <lastName>Peeters</lastName>
        <email>jan@example.com</email>
        <badgeCode>BADGE001</badgeCode>
        <role>VISITOR</role>
    </KassaUserCreated>""")


def test_kassa_user_created_invalid_uuid():
    invalid_kassa("""<KassaUserCreated>
        <userId>geen-uuid</userId>
        <firstName>Jan</firstName>
        <lastName>Peeters</lastName>
        <email>jan@example.com</email>
        <badgeCode>BADGE001</badgeCode>
        <role>VISITOR</role>
        <createdAt>2026-04-18T10:00:00Z</createdAt>
    </KassaUserCreated>""")


# ── Contract 37 — KassaUserUpdated ────────────────────────────────────────────

def test_kassa_user_updated_valid():
    valid_kassa("""<KassaUserUpdated>
        <userId>550e8400-e29b-4ed4-a716-446655440000</userId>
        <firstName>Jan</firstName>
        <lastName>Peeters</lastName>
        <email>jan@example.com</email>
        <badgeCode>BADGE001</badgeCode>
        <role>CASHIER</role>
        <updatedAt>2026-04-18T10:00:00Z</updatedAt>
    </KassaUserUpdated>""")


def test_kassa_user_updated_missing_updated_at():
    invalid_kassa("""<KassaUserUpdated>
        <userId>550e8400-e29b-4ed4-a716-446655440000</userId>
        <firstName>Jan</firstName>
        <lastName>Peeters</lastName>
        <email>jan@example.com</email>
        <badgeCode>BADGE001</badgeCode>
        <role>CASHIER</role>
    </KassaUserUpdated>""")


def test_kassa_user_updated_empty_first_name():
    """firstName mag niet leeg zijn (NonEmptyStringType)."""
    invalid_kassa("""<KassaUserUpdated>
        <userId>550e8400-e29b-4ed4-a716-446655440000</userId>
        <firstName></firstName>
        <lastName>Peeters</lastName>
        <email>jan@example.com</email>
        <badgeCode>BADGE001</badgeCode>
        <role>CASHIER</role>
        <updatedAt>2026-04-18T10:00:00Z</updatedAt>
    </KassaUserUpdated>""")


# ── Contract 38 — UserDeactivated (Kassa producer) ────────────────────────────

def test_kassa_user_deactivated_valid():
    """C38 gebruikt <id> (niet <userId>) als sleutelveld."""
    valid_kassa("""<UserDeactivated>
        <id>550e8400-e29b-4ed4-a716-446655440000</id>
        <email>jan@example.com</email>
        <deactivatedAt>2026-04-18T10:00:00Z</deactivatedAt>
    </UserDeactivated>""")


def test_kassa_user_deactivated_missing_email():
    invalid_kassa("""<UserDeactivated>
        <id>550e8400-e29b-4ed4-a716-446655440000</id>
        <deactivatedAt>2026-04-18T10:00:00Z</deactivatedAt>
    </UserDeactivated>""")


def test_kassa_user_deactivated_wrong_field_name():
    """userId in plaats van id is fout voor C38."""
    invalid_kassa("""<UserDeactivated>
        <userId>550e8400-e29b-4ed4-a716-446655440000</userId>
        <email>jan@example.com</email>
        <deactivatedAt>2026-04-18T10:00:00Z</deactivatedAt>
    </UserDeactivated>""")
