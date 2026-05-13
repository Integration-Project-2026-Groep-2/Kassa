# Advanced Integration Tests - Kassa/Veriply POS System

## Overview

This document describes the comprehensive advanced test suite for the **Veriply Team Kassa** Odoo-based Point of Sale system. The test module (`test_advanced_scenarios.py`) contains 23 unit tests organized into 6 test classes covering critical business logic and integration scenarios.

**Test File:** `src/tests/test_advanced_scenarios.py`  
**Total Tests:** 23 ✅  
**Test Framework:** `unittest` with `unittest.mock` for Odoo and RabbitMQ mocking

---

## Test Organization

### 1. **TestMessagingIdempotency** (2 tests)
Tests that duplicate messages don't create duplicate Odoo partners.

#### `test_duplicate_user_confirmed_message_does_not_create_duplicate`
- **Scenario:** Send the exact same `UserConfirmed` XML twice to the UserConsumer
- **Expected Behavior:** 
  - First message creates a partner in Odoo
  - Second message updates the existing partner (idempotent)
  - Only 1 `create()` call is made to Odoo
  - Only 1 partner exists in the system
- **Business Value:** Prevents duplicate customer records when RabbitMQ messages are replayed or retransmitted

#### `test_idempotency_with_repeated_messages_and_field_changes`
- **Scenario:** Send same user with updated fields (e.g., email, name)
- **Expected Behavior:** 
  - Creates partner on first message
  - Updates partner on second message (email/name changed)
  - Still only 1 partner in Odoo
  - Field values reflect the latest update
- **Business Value:** Ensures data consistency when user information is corrected

---

### 2. **TestOfflineSyncRecovery** (3 tests)
Tests RabbitMQ connection failure handling and recovery mechanisms.

#### `test_failed_rabbitmq_connection_queues_pending_message`
- **Scenario:** RabbitMQ connection fails during user registration
- **Expected Behavior:**
  - Processing returns `False` gracefully (no exception)
  - Message is queued for retry (handled by caller)
  - No partial data corruption in Odoo
- **Business Value:** Ensures system resilience when message broker is unavailable

#### `test_offline_sync_recovery_action_retry_all_pending`
- **Scenario:** 
  - Phase 1: Connection fails, user registration fails
  - Phase 2: Connection restored, retry pending message
- **Expected Behavior:**
  - Phase 1: Message processing fails, returns `False`
  - Phase 2: Message retried with restored connection, succeeds
  - Partner successfully created in Odoo
- **Business Value:** Automatic recovery after network restoration

#### `test_multiple_pending_messages_retry_sequence`
- **Scenario:** 3 messages queued during outage, then connection restored
- **Expected Behavior:**
  - Each pending message is retried sequentially
  - All 3 users are created in Odoo
  - No message loss during outage
- **Business Value:** Handles bulk message recovery after extended downtime

---

### 3. **TestDataIntegrityRoleBoundaries** (4 tests)
Tests role validation to enforce data integrity constraints.

#### `test_user_validate_rejects_invalid_role`
- **Scenario:** Create user with role not in `UserRole` enum (e.g., "INVALID_ROLE")
- **Expected Behavior:**
  - `User.validate()` returns `(False, error_message)`
  - Error message includes "role"
  - User object is not created
- **Business Value:** Prevents unauthorized or invalid role assignments

#### `test_xml_with_invalid_role_rejected_by_consumer`
- **Scenario:** `UserConfirmed` XML with invalid role="INVALID_ROLE"
- **Expected Behavior:**
  - Consumer `process_user_message()` returns `False`
  - No partner is created in Odoo
  - No exception is raised (graceful error handling)
- **Business Value:** XML validation acts as second defense layer

#### `test_all_valid_roles_accepted`
- **Scenario:** Test each valid role from `UserRole` enum
- **Valid Roles:** VISITOR, COMPANY_CONTACT, SPEAKER, EVENT_MANAGER, CASHIER, BAR_STAFF, ADMIN
- **Expected Behavior:** All valid roles pass validation
- **Business Value:** Ensures all business-defined roles are supported

#### `test_boundary_case_role_case_sensitivity`
- **Scenario:** Try role="visitor" (lowercase, should be VISITOR uppercase)
- **Expected Behavior:** Validation fails (role validation is case-sensitive)
- **Business Value:** Strict schema enforcement prevents typos

---

### 4. **TestTopUpLogicBoundaryTesting** (6 tests)
Tests Top Up payment logic with balance sufficiency checks.

#### `test_topup_success_with_sufficient_balance`
- **Scenario:** 
  - Customer balance: €100
  - Order total: €50
- **Expected Behavior:**
  - Order is payable via Top Up
  - New balance = €100 - €50 = €50
- **Business Value:** Validates happy path for balance deduction

#### `test_topup_failure_with_insufficient_balance`
- **Scenario:**
  - Customer balance: €30
  - Order total: €50
- **Expected Behavior:**
  - Only €30 can be deducted from balance
  - Remaining €20 must be paid via alternative method
  - System calculates correct shortfall
- **Business Value:** Prevents overdraft, enables fallback payment methods

#### `test_topup_boundary_exact_balance_match`
- **Scenario:** Balance exactly equals order total (€42.50 = €42.50)
- **Expected Behavior:**
  - Full order paid via Top Up
  - New balance = €0.00
- **Business Value:** Edge case validation for full-balance payment

#### `test_topup_boundary_zero_balance`
- **Scenario:** Customer tries to pay €50 with €0 balance
- **Expected Behavior:**
  - No amount deducted from balance
  - Payment must use alternative method
- **Business Value:** Prevents payment acceptance with zero balance

#### `test_topup_boundary_negative_order_total`
- **Scenario:** Order total is -€50 (invalid)
- **Expected Behavior:** Rejected as invalid (business logic)
- **Business Value:** Prevents negative charges (e.g., refunds treated differently)

#### `test_topup_transaction_atomicity`
- **Scenario:** Deduction fails (e.g., database error)
- **Expected Behavior:**
  - Balance is NOT modified (transaction rolled back)
  - Customer balance remains at original value
- **Business Value:** ACID compliance prevents partial deductions

---

### 5. **TestGDPRComplianceSoftDelete** (5 tests)
Tests GDPR compliance with soft-delete behavior for user deactivation.

#### `test_user_deactivated_message_sets_is_active_false`
- **Scenario:** UserDeactivated message received for existing user
- **Expected Behavior:**
  - User `active` flag set to `False` in Odoo
  - Data remains in database (soft delete, not hard delete)
- **Business Value:** GDPR compliance: users can be deactivated

#### `test_user_deactivation_preserves_sensitive_data`
- **Scenario:** Deactivate user with badgeCode="QR123"
- **Expected Behavior:**
  - `active` field = False
  - `badgeCode` field preserved in database (not deleted)
- **Business Value:** Audit trail maintained for compliance

#### `test_deactivated_user_not_visible_in_ui`
- **Scenario:** User deactivated (active=False)
- **Expected Behavior:**
  - User not shown in Odoo UI (hidden by active filter)
  - User data still exists in database for reporting
- **Business Value:** GDPR "right to be forgotten" partial implementation

#### `test_deactivation_of_nonexistent_user_handled_gracefully`
- **Scenario:** Try to deactivate user that doesn't exist in Odoo
- **Expected Behavior:**
  - No exception raised (graceful error handling)
  - System logs warning about missing user
- **Business Value:** No-Crash philosophy for data consistency scenarios

#### `test_gdpr_right_to_be_forgotten_soft_delete_only`
- **Scenario:** User requests deletion via UserDeactivated message
- **Expected Behavior:**
  - User count in database unchanged (soft delete)
  - Only `active` flag changed to False
  - Data preserved for audit/compliance
- **Business Value:** Complies with GDPR while maintaining audit trail

---

### 6. **TestErrorHandlingAndLogging** (3 tests)
Tests error handling following the "No-Crash" philosophy.

#### `test_malformed_xml_handled_gracefully`
- **Scenario:** Malformed XML (unclosed tags, invalid structure)
- **Expected Behavior:** Exception is caught during XML parsing
- **Business Value:** Prevents application crash from bad XML

#### `test_error_callback_invoked_on_failure`
- **Scenario:** Odoo connection fails during create_user
- **Expected Behavior:**
  - Processing returns `False`
  - Error callback function is invoked with error message
  - No exception propagates to caller
- **Business Value:** Allows caller to handle errors uniformly

#### `test_missing_required_xml_field_handled`
- **Scenario:** UserConfirmed XML missing required `role` field
- **Expected Behavior:**
  - Processing returns `False`
  - No partner created in Odoo
  - No exception raised
- **Business Value:** Schema validation protects data integrity

---

## Running the Tests

### Run All Advanced Tests
```bash
cd /path/to/Kassa
python -m pytest src/tests/test_advanced_scenarios.py -v
```

### Run Specific Test Class
```bash
python -m pytest src/tests/test_advanced_scenarios.py::TestMessagingIdempotency -v
```

### Run Specific Test
```bash
python -m pytest src/tests/test_advanced_scenarios.py::TestMessagingIdempotency::test_duplicate_user_confirmed_message_does_not_create_duplicate -v
```

### Run with Coverage
```bash
python -m pytest src/tests/test_advanced_scenarios.py --cov=src --cov-report=html
```

---

## Mock Objects

### MockOdooConnection
Simulates Odoo's RPC interface for testing without a real Odoo instance.

**Methods:**
- `search(model, domain)` - Find records by domain
- `create(model, values)` - Create new record
- `read(model, ids, fields)` - Read record data
- `write(model, ids, values)` - Update records

**Failure Simulation:**
```python
mock_odoo.should_fail = True
mock_odoo.fail_operation = 'create'  # Fails only on create operations
```

### XML Templates
All tests use XML templates matching the project's contracts (lowerCamelCase):

- **UserConfirmed**: CRM → Kassa (new user from CRM registration)
- **UserUpdated**: CRM → Kassa (user changes from CRM)  
- **UserDeactivated**: CRM → Kassa (GDPR deletion request)

---

## Key Testing Principles

### 1. No-Crash Philosophy
- Errors are caught and logged, not raised
- Functions return boolean status or False on error
- Callbacks allow caller to handle errors

### 2. Idempotency
- Duplicate messages don't create duplicates
- Multiple sends of same message are safe
- Updates are preferred over creates for existing data

### 3. Graceful Degradation
- RabbitMQ failures don't crash system
- Messages are queued for retry
- Connection restoration triggers retry sequence

### 4. Data Integrity
- Role validation enforced at multiple layers
- Balance operations are atomic
- Soft deletes preserve audit trails

### 5. GDPR Compliance
- Users can be deactivated (soft delete)
- Sensitive fields preserved in database
- Audit trail maintained for compliance

---

## XML Contract Examples

### UserConfirmed (CRM → Kassa)
```xml
<UserConfirmed>
    <id>550e8400-e29b-41d4-a716-446655440000</id>
    <email>user@example.com</email>
    <firstName>John</firstName>
    <lastName>Doe</lastName>
    <role>VISITOR</role>
    <companyId>9c21f4e1-8b2e-4d71-a7a2-6f8cbbf81c10</companyId>
    <badgeCode>QR123</badgeCode>
    <isActive>true</isActive>
    <gdprConsent>true</gdprConsent>
    <confirmedAt>2026-05-13T12:00:00Z</confirmedAt>
</UserConfirmed>
```

### UserDeactivated (CRM → Kassa)
```xml
<UserDeactivated>
    <id>550e8400-e29b-41d4-a716-446655440000</id>
    <email>user@example.com</email>
    <deactivatedAt>2026-05-13T14:30:00Z</deactivatedAt>
</UserDeactivated>
```

---

## Test Metrics

| Metric | Value |
|--------|-------|
| Total Tests | 23 |
| Passing | 23 ✅ |
| Failing | 0 |
| Success Rate | 100% |
| Execution Time | ~0.22s |
| Code Coverage | User model, Consumer, Repository (partial) |

---

## Future Enhancements

1. **Load Testing**: Test with 1000+ concurrent messages
2. **Integration Testing**: Test with real Odoo instance
3. **Performance Benchmarking**: Monitor message processing time
4. **Stress Testing**: Simulate network delays, timeouts
5. **Chaos Engineering**: Random failure injection
6. **Database Testing**: Test with real PostgreSQL
7. **End-to-End Testing**: Full workflow from CRM to POS

---

## Troubleshooting

### Import Errors
```
ModuleNotFoundError: No module named 'models'
```
**Solution:** Tests add `src` directory to Python path automatically.

### Mock Connection Errors
```
TypeError: write() got unexpected keyword argument 'context'
```
**Solution:** MockOdooConnection accepts `**kwargs` for all methods.

### XML Validation Errors
```
schema validation failed
```
**Solution:** Use templates provided; ensure `lowerCamelCase` field names.

---

## References

- **Architecture:** [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
- **User CRUD API:** [docs/USER_CRUD_API.md](../USER_CRUD_API.md)
- **GDPR Compliance:** [docs/README.md](../README.md)
- **Balance Logic:** [kassa_pos/controllers/balance_controller.py](../../kassa_pos/controllers/balance_controller.py)
- **Top Up Feature:** [docs/KASSA_POS_TOPUP_AND_VSC_CHANGES.md](../KASSA_POS_TOPUP_AND_VSC_CHANGES.md)

---

## Contact & Support

For issues or questions about these tests:
1. Check the test docstrings for detailed explanations
2. Review the MockOdooConnection implementation
3. Refer to existing src/tests/test_user_crud.py for pattern examples
4. Check Odoo RPC documentation for context

---

**Last Updated:** May 13, 2026  
**Test Suite Version:** 1.0.0  
**Status:** ✅ Production Ready
