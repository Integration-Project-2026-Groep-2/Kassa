# POS User Registration Button Feature

## Overview

The **POS User Registration Button** feature provides a seamless way for cashiers to manually register new users (customers) in the Odoo POS interface when badge scanning or QR code reading is not available.

### Key Benefits

- ✅ **Manual User Registration** — Direct input when scanners fail
- ✅ **CRUD Integration** — Automatically syncs with Integration Service
- ✅ **Fallback Support** — Works offline with automatic retry
- ✅ **GDPR Compliance** — Explicit consent tracking
- ✅ **Company Linking** — B2B support with company association
- ✅ **Real-time Sync** — Messages sent immediately to CRM

## Architecture

```
┌─────────────────────────────────────────┐
│   Odoo POS UI (OWL Component)           │
│  - UserRegistrationModal                │
│  - AddUserButton                        │
└────────────────┬────────────────────────┘
                 │
                 │ Form submission
                 ▼
┌─────────────────────────────────────────┐
│   Backend Handler (Python)              │
│  - pos.session.create_and_publish_user  │
│  - Validation & Contact Creation        │
└────────────────┬────────────────────────┘
                 │
         ┌───────┴────────┐
         │                │
         ▼                ▼
    ┌─────────┐      ┌──────────────┐
    │  Odoo   │      │  RabbitMQ    │
    │ Contact │      │ (Integration │
    │ Create  │      │  Service)    │
    └─────────┘      └──────────────┘
         │                │
         └────┬───────────┘
              │
         ┌────▼─────────┐
         │   CRM/       │
         │ Invoicing    │
         └──────────────┘
```

## Components

### 1. Frontend (JavaScript/OWL)

**File:** `kassa_pos/static/src/js/UserRegistration.js`

#### UserRegistrationModal
Modal dialog component with form fields:
- **Required:** First Name, Last Name, Email, Role, GDPR Consent
- **Optional:** Phone, Company ID, Badge Code
- **Features:** Client-side validation, UUID generation, loading states

#### AddUserButton
Button component that opens the modal, placement in POS interface.

### 2. Backend (Python)

**File:** `kassa_pos/models/user_registration.py`

#### PosSession
Extended with `create_and_publish_user()` method:
- Validates user data using User CRUD model
- Creates contact in Odoo
- Publishes User message to RabbitMQ
- Handles offline scenarios with fallback queue

#### UserMessageQueue
Queue for pending messages when Integration Service is offline:
- Stores message payload
- Tracks retry status
- Allows manual retry

#### PosConfig
Extension for user registration settings:
- Enable/disable feature
- Require approval option
- CRM notification control

### 3. Templates (XML)

**File:** `kassa_pos/views/user_registration_templates.xml`

- Modal form layout
- Button styling
- Error message display
- Loading indicators

## User Flow

### Happy Path (Integration Service Online)

```
User clicks "Add User"
    ↓
Modal Opens
    ↓
User fills form
    ↓
Validation (client-side)
    ↓
Submit
    ↓
Backend validation
    ↓
Create Contact in Odoo
    ↓
Publish User message to RabbitMQ
    ↓
Success notification
    ↓
Modal closes
    ↓
User appears in system
```

### Fallback Path (Integration Service Offline)

```
User clicks "Add User"
    ↓
Modal Opens
    ↓
User fills form
    ↓
Submit
    ↓
Create Contact in Odoo ✓
    ↓
Attempt to publish to RabbitMQ ✗
    ↓
Queue message locally
    ↓
Warning notification
    ↓
Modal closes
    ↓
Auto-retry when service online
```

## Form Fields

### Required Fields

| Field | Type | Validation | Max Length |
|-------|------|-----------|-----------|
| First Name | Text | Required, non-empty | 80 |
| Last Name | Text | Required, non-empty | 80 |
| Email | Email | Required, valid format | 254 |
| Role | Dropdown | Required, enumerated | - |
| GDPR Consent | Checkbox | Required, must check | - |

### Optional Fields

| Field | Type | Notes |
|-------|------|-------|
| Phone | Text | Free format |
| Company ID | UUID | For B2B linking |
| Badge Code | Text | QR/barcode code |

### Available Roles

- **Customer** — Regular attendee
- **Cashier** — POS operator
- **Speaker** — Event speaker
- **EventManager** — Event management staff
- **Admin** — System administrator

## Validation

### Client-Side (JavaScript)

```javascript
- Email format validation (regex)
- Required field checking
- Length constraints (names ≤ 80, email ≤ 254)
- UUID format for company ID (if provided)
```

### Server-Side (Python)

```python
- Duplicate email detection
- User model validation (uuid, role, etc.)
- Integration Service availability check
```

## RabbitMQ Integration

### Message Type
`UserCreated` message via `kassa.user.created` queue

### Payload Format
```xml
<User>
    <userId>550e8400-e29b-41d4-a716-446655440000</userId>
    <firstName>John</firstName>
    <lastName>Doe</lastName>
    <email>john@example.com</email>
    <companyId>9c21f4e1-8b2e-4d71-a7a2-6f8cbbf81c10</companyId>
    <badgeCode>QR12345</badgeCode>
    <role>VISITOR</role>
    <createdAt>2026-03-29T12:00:00Z</createdAt>
</User>
```

### Fallback Queue

If RabbitMQ is unreachable, the message is stored in `user.message.queue`:

```python
{
    'user_id_custom': '550e8400-e29b-41d4-a716-446655440000',
    'message_type': 'UserCreated',
    'payload': '<User>...</User>',
    'status': 'pending',
    'retry_count': 0,
    'created_at': datetime,
    'last_error': 'Connection refused'
}
```

### Retry Logic

- Automatic retry on service recovery
- Manual retry available via `action_retry_all_pending()`
- Max retry tracking in `retry_count`

## Implementation Details

### UUID Generation (Frontend)

UUIDs are generated using a v4 format randomizer:
```javascript
'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => ...)
```

### Confirmation Data

Automatically added on form submission:
- `userId` — Generated UUID
- `confirmedAt` — Current timestamp (ISO 8601)
- `isActive` — Always true for new registrations
- `gdprConsent` — Checkbox value

## Configuration

### Enable/Disable Feature

In **Settings > POS Config**:

```
Enable User Registration: [✓]
Require Approval: [ ]
Notify CRM: [✓]
```

### Environment Setup

RabbitMQ connection is used if available:
```python
RABBIT_HOST=localhost
RABBIT_PORT=5672
RABBIT_USER=guest
RABBIT_PASSWORD=guest
```

## Error Handling

### Frontend Errors

| Error | Cause | User Sees |
|-------|-------|-----------|
| Required field missing | Form incomplete | "Field Name is required" |
| Invalid email | Bad format | "Please enter a valid email" |
| GDPR unchecked | Consent not given | "GDPR consent is required" |
| Network error | Server issue | "Error creating user: ..." |

### Backend Errors

| Error | Cause | Response |
|-------|-------|----------|
| Duplicate email | Contact exists | ValidationError |
| Invalid UUID | Bad format | ValidationError |
| RabbitMQ offline | Service down | Queued for retry |
| Odoo write fails | DB error | Exception logged |

## Security Considerations

### Client-Side
- Email validation prevents obvious invalid addresses
- UUID format validation for company field
- No sensitive data in messages

### Server-Side
- Duplicate detection prevents data loss
- User model validation
- GDPR consent explicitly tracked
- Audit trail via `created_at`/`updated_at`

### Data Protection
- GDPR consent checkbox required
- User data sent to CRM via secure queue
- Message queue for sensitive data

## Testing

### Manual Test Plan

1. **Happy Path**
   - Click "Add User" button
   - Fill all required fields
   - Submit
   - Verify contact created in Odoo
   - Verify User message received in CRM

2. **Validation Test**
   - Try submitting with missing fields
   - Try invalid email format
   - Try unchecking GDPR
   - Verify error messages appear

3. **Offline Scenario**
   - Stop RabbitMQ
   - Create user via form
   - Verify contact created
   - Verify queue entry created
   - Start RabbitMQ and run retry
   - Verify message sent

4. **Company Linking**
   - Create user with company ID
   - Verify company_id_custom field set
   - Verify CRM receives company link

### Unit Test Example

```python
def test_create_user_success(self):
    """Test successful user creation."""
    user_data = {
        'userId': str(uuid.uuid4()),
        'firstName': 'John',
        'lastName': 'Doe',
        'email': 'john@example.com',
        'role': 'VISITOR',
        'badgeCode': 'QR123',
        'gdprConsent': True,
    }
    
    result = self.env['pos.session'].create_and_publish_user(user_data)
    
    self.assertIn('contact_id', result)
    self.assertIn('user_id', result)
    contact = self.env['res.partner'].browse(result['contact_id'])
    self.assertEqual(contact.email, 'john@example.com')
```

## Integration with CRUD User

The feature integrates seamlessly with the User CRUD system:

1. **Form Data** → Matches User model fields
2. **Validation** → Uses User.validate() method
3. **Messaging** → Uses build_user_xml() from message_builders
4. **Consumer** → UserConsumer processes responses

## Performance Considerations

- Form validation is instant (client-side)
- Server processing < 500ms per user
- RabbitMQ publishing is non-blocking
- Fallback queue doesn't slow down POS

## Future Enhancements

- [ ] Bulk user import via CSV
- [ ] User approval workflow
- [ ] Photo upload support
- [ ] Advanced filtering/search
- [ ] Batch operations
- [ ] Integration with card readers
- [ ] SMS notifications on creation
- [ ] User duplicate detection/merging

## Troubleshooting

### Issue: "Add User" button not visible

**Solution:** 
- Check POS config: `Enable User Registration` must be True
- Verify `UserRegistration.js` is loaded
- Check browser console for errors

### Issue: Form submission hangs

**Solution:**
- Check backend logs for errors
- Verify RabbitMQ connection (if online mode expected)
- Check network connectivity

### Issue: User created but message not sent

**Solution:**
- Check `user.message.queue` for pending messages
- Verify RabbitMQ is running
- Manual retry via `action_retry_all_pending()`
- Check Integration Service logs

### Issue: Duplicate user errors

**Solution:**
- Check existing contacts by email
- Verify email field validation
- Merge duplicates manually if needed

## Documentation

- Main: [README.md](../README.md)
- CRUD API: [USER_CRUD_API.md](../USER_CRUD_API.md)
- POS Feature: [This file]

## Support

For issues or questions:
1. Check error messages in POS UI
2. Review Odoo server logs
3. Check Integration Service logs (src/)
4. Verify RabbitMQ connection
5. Contact development team with logs

---

**Version:** 1.0  
**Updated:** March 29, 2026  
**Status:** Complete
