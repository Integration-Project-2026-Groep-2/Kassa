# POS User Registration API Reference

## Table of Contents

1. [Frontend API (JavaScript/OWL)](#frontend-api)
2. [Backend API (Python/Odoo)](#backend-api)
3. [Message Format (XML)](#message-format)
4. [Error Codes & Handling](#error-codes)
5. [Code Examples](#code-examples)

---

## Frontend API

### UserRegistrationModal

OWL component for the registration modal dialog.

#### Properties

```javascript
class UserRegistrationModal {
    // Data properties
    formData = {
        firstName: '',
        lastName: '',
        email: '',
        phone: '',
        role: 'VISITOR',
        companyId: '',
        badgeCode: '',
        gdprConsent: false,
    };
    
    isLoading = false;
    errorMessage = '';
}
```

#### Methods

##### validateForm()

Validates all form fields before submission.

```javascript
validateForm(): boolean
```

**Returns:**
- `true` — All fields valid, ready to submit
- `false` — One or more validation errors

**Validates:**
- Required fields: firstName, lastName, email, role, gdprConsent
- Email format: RFC 5322 regex pattern
- Field lengths: names ≤ 80, email ≤ 254
- Company ID format: Valid UUID if provided
- GDPR: Checkbox must be checked

**Example:**
```javascript
if (this.validateForm()) {
    this.onSubmit();
}
```

##### generateUUID()

Generates a UUID v4 identifier for the new user.

```javascript
generateUUID(): string
```

**Returns:**
- UUID v4 string like `"550e8400-e29b-41d4-a716-446655440000"`

**Used by:** `onSubmit()` to create userId field

**Example:**
```javascript
const userId = this.generateUUID();
// Returns: "a1b2c3d4-e5f6-4g7h-8i9j-k0l1m2n3o4p5"
```

##### mapRoleToOdoo(role)

Maps registration role names to Odoo partner category codes.

```javascript
mapRoleToOdoo(role: string): string
```

**Input Roles:**
- `"VISITOR"` → Default, no category
- `"SPEAKER"` → Category: `speaker_category`
- `"ORGANIZER"` → Category: `organizer_category`
- `"SPONSOR"` → Category: `sponsor_category`
- `"CASHIER"` → Category: `cashier_category`

**Returns:**
- Odoo category code string
- Empty string if no mapping

**Example:**
```javascript
const odooRole = this.mapRoleToOdoo('SPEAKER');
// Returns: "speaker_category"
```

##### onSubmit()

Handles form submission with validation and server communication.

```javascript
async onSubmit(): Promise<void>
```

**Process:**
1. Validate form fields
2. Generate UUID for userId
3. Collect user data
4. Create contact in Odoo via ORM
5. Publish message to Integration Service
6. Handle response/errors

**Throws:**
- `ValidationError` — Form validation failed
- `ServerError` — Contact creation failed
- `NetworkError` — RabbitMQ publish failed

**Example:**
```javascript
async onSubmit() {
    try {
        if (!this.validateForm()) return;
        
        const userId = this.generateUUID();
        const userData = {
            userId: userId,
            firstName: this.formData.firstName.trim(),
            lastName: this.formData.lastName.trim(),
            email: this.formData.email.trim(),
            badgeCode: this.formData.badgeCode || `USER_${userId}`,
            role: this.mapRoleToOdoo(this.formData.role),
            gdprConsent: this.formData.gdprConsent,
            confirmedAt: new Date().toISOString(),
        };
        
        const contactId = await this.orm.create('res.partner', [
            // Contact data
        ]);
        
        const response = await this.rpc.call(
            'pos.session',
            'create_and_publish_user',
            { user_data: userData }
        );
        
        this.notification.add('User created successfully', { type: 'success' });
        this.closeModal();
    } catch (error) {
        this.errorMessage = error.message;
        this.notification.add(error.message, { type: 'danger' });
    }
}
```

### AddUserButton

Button component to trigger the registration modal.

```javascript
class AddUserButton {
    openModal(): void {
        // Opens UserRegistrationModal
    }
}
```

**Usage in template:**
```xml
<AddUserButton />
```

---

## Backend API

### PosSession Model Extension

Extended with user registration methods.

#### create_and_publish_user(user_data)

Main entry point for creating and publishing users.

```python
@api.model
def create_and_publish_user(self, user_data: dict) -> dict
```

**Input:**
```python
{
    'userId': '550e8400-e29b-41d4-a716-446655440000',
    'firstName': 'John',
    'lastName': 'Doe',
    'email': 'john@example.com',
    'badgeCode': 'QR123456',
    'role': 'VISITOR',
    'companyId': '9c21f4e1-8b2e-4d71-a7a2-6f8cbbf81c10',
    'gdprConsent': True,
    'confirmedAt': '2026-03-29T12:00:00Z',
}
```

**Returns:**
```python
{
    'contact_id': 42,
    'user_id': '550e8400-e29b-41d4-a716-446655440000',
    'email': 'john@example.com',
    'status': 'published' or 'queued',
}
```

**Raises:**
- `ValidationError` — Invalid user data
- `UserWarning` — RabbitMQ offline (queued for retry)
- `Exception` — Unexpected error

**Process:**
1. Validates user data via User model
2. Creates/updates contact if needed
3. Publishes to RabbitMQ integration.user.created queue
4. On failure: Queues message in user.message.queue

**Example:**
```python
session = self.env['pos.session'].browse(session_id)
result = session.create_and_publish_user({
    'userId': '550e8400-e29b-41d4-a716-446655440000',
    'firstName': 'Jane',
    'lastName': 'Smith',
    'email': 'jane@example.com',
    'role': 'CASHIER',
    'badgeCode': 'CASHIER_001',
    'gdprConsent': True,
    'confirmedAt': datetime.now().isoformat(),
})

if result['status'] == 'published':
    print(f"User {result['user_id']} created and sent to CRM")
elif result['status'] == 'queued':
    print(f"User {result['user_id']} queued for retry")
```

### UserMessageQueue Model

Queue for pending messages when Integration Service is offline.

#### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| user_id_custom | Char | Yes | UUID of the user |
| message_type | Selection | Yes | UserCreated, UserUpdated, etc. |
| payload | Text | Yes | XML message body |
| status | Selection | Yes | pending, sent, failed |
| retry_count | Integer | No | Number of retry attempts |
| created_at | Datetime | Yes | When queued |
| last_error | Text | No | Error message from last attempt |

#### action_retry_all_pending()

Retries all pending messages in the queue.

```python
def action_retry_all_pending(self) -> dict
```

**Returns:**
```python
{
    'total': 5,
    'success': 4,
    'failed': 1,
}
```

**Example:**
```python
queue = self.env['user.message.queue']
pending = queue.search([('status', '=', 'pending')])
result = pending.action_retry_all_pending()
print(f"Retried {result['total']} messages: {result['success']} success")
```

### User Model (CRUD System)

Core user validation used by registration.

```python
from src.models.user import User, UserStore

# Create new user
user = User(
    user_id='550e8400-e29b-41d4-a716-446655440000',
    first_name='John',
    last_name='Doe',
    email='john@example.com',
    badge_code='QR123',
    role='VISITOR',
    company_id='9c21f4e1-8b2e-4d71-a7a2-6f8cbbf81c10',
)

# Validate
try:
    errors = user.validate()
    if errors:
        raise ValueError(f"Validation errors: {errors}")
except ValidationError as e:
    print(f"Invalid user: {e}")
```

### Message Builders

Convert user data to XML format for RabbitMQ.

#### build_user_xml(user_data)

Creates XML representation of user data.

```python
from src.messaging.message_builders import build_user_xml

xml_string = build_user_xml({
    'userId': '550e8400-e29b-41d4-a716-446655440000',
    'firstName': 'John',
    'lastName': 'Doe',
    'email': 'john@example.com',
    'badgeCode': 'QR123',
    'role': 'VISITOR',
    'companyId': '9c21f4e1-8b2e-4d71-a7a2-6f8cbbf81c10',
    'createdAt': '2026-03-29T12:00:00Z',
})

# Returns XML string:
# <User>
#     <userId>550e8400-e29b-41d4-a716-446655440000</userId>
#     <firstName>John</firstName>
#     ...
# </User>
```

#### parse_user_xml(xml_string)

Parses XML string back to dictionary.

```python
from src.messaging.message_builders import parse_user_xml

user_dict = parse_user_xml("""
<User>
    <userId>550e8400-e29b-41d4-a716-446655440000</userId>
    <firstName>John</firstName>
    <lastName>Doe</lastName>
    <email>john@example.com</email>
</User>
""")

# Returns:
# {
#     'userId': '550e8400-e29b-41d4-a716-446655440000',
#     'firstName': 'John',
#     'lastName': 'Doe',
#     'email': 'john@example.com',
# }
```

---

## Message Format

### Request: UserCreated

Published from POS to CRM system.

```xml
<User>
    <userId>550e8400-e29b-41d4-a716-446655440000</userId>
    <firstName>John</firstName>
    <lastName>Doe</lastName>
    <email>john@example.com</email>
    <companyId>9c21f4e1-8b2e-4d71-a7a2-6f8cbbf81c10</companyId>
    <badgeCode>QR123456</badgeCode>
    <role>VISITOR</role>
    <createdAt>2026-03-29T12:00:00Z</createdAt>
</User>
```

**Schema Location:** `src/schema/kassa-schema-v1.xsd`

**Queue:** `integration.user.created`

**Example in code:**
```python
xml = """
<User>
    <userId>550e8400-e29b-41d4-a716-446655440000</userId>
    <firstName>John</firstName>
    <lastName>Doe</lastName>
    <email>john@example.com</email>
    <role>VISITOR</role>
    <createdAt>2026-03-29T12:00:00Z</createdAt>
</User>
"""
await publisher.publish(xml, routing_key='integration.user.created')
```

---

## Error Codes

### Validation Errors

| Code | Message | Cause | Solution |
|------|---------|-------|----------|
| `ERR_FIRST_NAME_REQUIRED` | First name required | Missing firstName | Provide first name |
| `ERR_LAST_NAME_REQUIRED` | Last name required | Missing lastName | Provide last name |
| `ERR_EMAIL_REQUIRED` | Email required | Missing email | Provide email |
| `ERR_EMAIL_INVALID` | Invalid email format | Bad email format | Use valid email format |
| `ERR_EMAIL_DUPLICATE` | Email already exists | User exists | Use different email |
| `ERR_ROLE_INVALID` | Invalid role | Unknown role | Use valid role name |
| `ERR_GDPR_REQUIRED` | GDPR consent required | Consent not checked | Check GDPR consent |
| `ERR_UUID_INVALID` | Invalid UUID format | Bad UUID | Use valid UUID format |

### System Errors

| Code | Message | Cause | Solution |
|------|---------|-------|----------|
| `ERR_CONTACT_CREATE_FAILED` | Failed to create contact | Odoo DB error | Check database logs |
| `ERR_RABBITMQ_OFFLINE` | RabbitMQ offline | Connection failed | Start RabbitMQ, message queued |
| `ERR_NETWORK_ERROR` | Network error | Connection issue | Check network, add to queue |
| `ERR_TIMEOUT` | Request timeout | Server slow | Retry request |

### Frontend Error Handling

```javascript
try {
    await this.onSubmit();
} catch (error) {
    if (error.code === 'ERR_EMAIL_DUPLICATE') {
        alert('Email already used. Use a different email.');
    } else if (error.code === 'ERR_RABBITMQ_OFFLINE') {
        alert('Service temporarily offline. Will retry automatically.');
    } else {
        alert(`Error: ${error.message}`);
    }
}
```

### Backend Error Handling

```python
from src.models.user import ValidationError

try:
    self.create_and_publish_user(user_data)
except ValidationError as e:
    logger.error(f"Validation failed: {e.errors}")
    raise UserWarning(f"Invalid user data: {e.errors[0]}")
except Exception as e:
    logger.exception("User creation failed")
    # Message will be queued for retry
    raise UserWarning("Failed to create user. Queued for retry.")
```

---

## Code Examples

### Example 1: Basic User Registration Flow

**Frontend (JavaScript):**
```javascript
// File: kassa_pos/static/src/js/UserRegistration.js

async onSubmit() {
    // Validate form
    if (!this.validateForm()) {
        this.errorMessage = 'Please fill all required fields';
        return;
    }
    
    try {
        this.isLoading = true;
        
        // Prepare user data
        const userId = this.generateUUID();
        const userData = {
            userId: userId,
            firstName: this.formData.firstName.trim(),
            lastName: this.formData.lastName.trim(),
            email: this.formData.email.trim(),
            badgeCode: this.formData.badgeCode || `USER_${userId}`,
            role: this.formData.role,
            companyId: this.formData.companyId,
            gdprConsent: this.formData.gdprConsent,
            confirmedAt: new Date().toISOString(),
        };
        
        // Create contact
        const contactData = {
            name: `${userData.firstName} ${userData.lastName}`,
            email: userData.email,
            phone: this.formData.phone,
            user_id_custom: userData.userId,
            badge_code: userData.badgeCode,
            role: userData.role,
        };
        
        const contactId = await this.orm.create('res.partner', [contactData]);
        
        // Publish to Integration Service
        const result = await this.rpc.call(
            'pos.session',
            'create_and_publish_user',
            { user_data: userData }
        );
        
        // Success
        this.notification.add('User registered successfully', { 
            type: 'success',
            title: 'Registration Complete',
        });
        
        this.closeModal();
    } catch (error) {
        this.errorMessage = error.message || 'An error occurred';
        this.notification.add(this.errorMessage, { 
            type: 'danger',
            title: 'Registration Failed',
        });
    } finally {
        this.isLoading = false;
    }
}
```

**Backend (Python):**
```python
# File: kassa_pos/models/user_registration.py

@api.model
def create_and_publish_user(self, user_data):
    """Create user and publish to Integration Service."""
    
    # 1. Validate user data
    from src.models.user import User
    user = User(
        user_id=user_data['userId'],
        first_name=user_data['firstName'],
        last_name=user_data['lastName'],
        email=user_data['email'],
        badge_code=user_data.get('badgeCode', ''),
        role=user_data['role'],
        company_id=user_data.get('companyId', ''),
    )
    
    errors = user.validate()
    if errors:
        raise ValidationError(f"Invalid user: {', '.join(errors)}")
    
    # 2. Create contact in Odoo
    contact = self.env['res.partner'].create({
        'name': f"{user_data['firstName']} {user_data['lastName']}",
        'email': user_data['email'],
        'phone': user_data.get('phone', ''),
        'user_id_custom': user_data['userId'],
        'badge_code': user_data['badgeCode'],
        'role': user_data['role'],
        'company_id_custom': user_data.get('companyId', ''),
        'is_company': False,
    })
    
    # 3. Build XML message
    from src.messaging.message_builders import build_user_xml
    xml_message = build_user_xml(user_data)
    
    # 4. Publish to RabbitMQ
    try:
        from src.messaging.producer import publish_message
        publish_message(xml_message, 'integration.user.created')
        return {
            'contact_id': contact.id,
            'user_id': user_data['userId'],
            'status': 'published',
        }
    except Exception as e:
        # Queue for retry
        self.env['user.message.queue'].create({
            'user_id_custom': user_data['userId'],
            'message_type': 'UserCreated',
            'payload': xml_message,
            'status': 'pending',
            'last_error': str(e),
        })
        
        return {
            'contact_id': contact.id,
            'user_id': user_data['userId'],
            'status': 'queued',
            'error': str(e),
        }
```

### Example 2: Handling RabbitMQ Response

**Backend (Integration Service):**
```python
# File: src/messaging/user_consumer.py

async def process_user_message(self, message_data):
    """Process incoming User message from CRM."""
    
    message_type = message_data.get('message_type')
    
    if message_type == 'User':
        # Store new user
        user = User(
            user_id=message_data['userId'],
            first_name=message_data['firstName'],
            last_name=message_data['lastName'],
            email=message_data['email'],
            badge_code=message_data.get('badgeCode', ''),
            role=message_data['role'],
            company_id=message_data.get('companyId', ''),
        )
        
        errors = user.validate()
        if errors:
            logger.warning(f"Invalid user: {errors}")
            return False
        
        # Add to store
        result = self.user_store.create(user)
        logger.info(f"User stored: {user.user_id}")
        return True
    
    elif message_type == 'UserConfirmed':
        # CRM acknowledged the user
        user_id = message_data['userId']
        user = self.user_store.read_by_id(user_id)
        if user:
            user.is_active = True
            logger.info(f"User confirmed: {user_id}")
        return True
    
    elif message_type == 'UserDeactivated':
        # GDPR delete request
        user_id = message_data['userId']
        if self.user_store.delete(user_id):
            logger.info(f"User deactivated: {user_id}")
        return True
```

### Example 3: Retry Pending Messages

**Manual Retry:**
```python
# From POS action
queue = self.env['user.message.queue']
pending = queue.search([('status', '=', 'pending')])

result = pending.action_retry_all_pending()
print(f"Retried {result['success']} of {result['total']} messages")
```

**Automatic Retry on Service Startup:**
```python
# In main_pos_receiver.py
def on_startup():
    """Retry pending messages when service starts."""
    queue = self.env['user.message.queue']
    pending = queue.search([('status', '=', 'pending')])
    if pending:
        logger.info(f"Retrying {len(pending)} pending messages")
        pending.action_retry_all_pending()
```

---

## Integration Points

### With User CRUD System
- Validates data using `User.validate()`
- Uses `UserStore` for checking duplicates
- Publishes via message builders

### With Odoo ORM
- Creates contacts via `res.partner.create()`
- Links to companies via `company_id_custom`
- Uses custom fields: `user_id_custom`, `badge_code`, `role`

### With RabbitMQ
- Publishes to `integration.user.created`
- Receives responses on `integration.user.confirmed`
- Falls back to `user.message.queue` when offline

### With CRM System
- Sends `User` messages
- Receives `UserConfirmed`, `UserUpdated`, `UserDeactivated` messages
- Tracks company links for B2B scenarios

---

## Version History

- **1.0** (March 29, 2026) — Initial release with User CRUD integration
- **1.1** (Planned) — Bulk import support
- **1.2** (Planned) — Photo uploads
- **1.3** (Planned) — Advanced filtering

---

**For questions or issues, contact the development team or check the main [README.md](../README.md)**
