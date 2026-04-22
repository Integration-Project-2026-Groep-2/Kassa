# User CRUD API Documentation

Quick reference guide for User CRUD operations in the Kassa Integration Service.

## Quick Start

### Import and Initialize

```python
from models.user import User, UserStore
from messaging.user_consumer import UserConsumer
from messaging.message_builders import build_user_xml, parse_user_xml

# Create store
store = UserStore()

# For message handling
consumer = UserConsumer(store)
```

## User Object

### Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `userId` | UUID | Yes | Auto-generated if empty |
| `firstName` | str | Yes | Max 80 chars |
| `lastName` | str | Yes | Max 80 chars |
| `email` | str | Yes | Valid email format |
| `badgeCode` | str | Yes | Unique |
| `role` | str | Yes | See roles below |
| `companyId` | UUID | Optional | For B2B linking |
| `createdAt` | ISO 8601 | Auto | Timestamp |
| `updatedAt` | ISO 8601 | Auto | Timestamp |

### Valid Roles

```
VISITOR           # Regular attendee
COMPANY_CONTACT   # Corporate contact
SPEAKER           # Event speaker
EVENT_MANAGER     # Management staff
CASHIER           # POS operator
BAR_STAFF         # Bar service
ADMIN             # System admin
```

## CRUD Operations

### CREATE

```python
from models.user import User

user = User(
    userId="550e8400-e29b-41d4-a716-446655440000",
    firstName="John",
    lastName="Doe",
    email="john@example.com",
    badgeCode="QR12345",
    role="VISITOR"
)

success, error, created_user = store.create_user(user)

if success:
    print(f"Created: {created_user.userId}")
else:
    print(f"Error: {error}")
```

**Error cases:**
- Duplicate `userId`
- Duplicate `badgeCode`
- Invalid email format
- Invalid role
- Missing required fields

### READ

```python
# By ID
user = store.get_user_by_id("550e8400-e29b-41d4-a716-446655440000")

# By badge code (scanner)
user = store.get_user_by_badge("QR12345")

# By email
user = store.get_user_by_email("john@example.com")

# All users
all_users = store.get_all_users()

# Check existence
if user is None:
    print("User not found")
```

### UPDATE

```python
success, error, updated_user = store.update_user(
    user_id="550e8400-e29b-41d4-a716-446655440000",
    updates={
        'firstName': 'Jane',
        'role': 'CASHIER',
        'badgeCode': 'QR54321'  # Changes index
    }
)

if success:
    print(f"Updated: {updated_user.firstName}")
else:
    print(f"Error: {error}")
```

**Important:**
- Updates are field-specific (no full replacement)
- Automatically updates `updatedAt` timestamp
- Changing `badgeCode` updates the index
- Validates all fields

### DELETE

```python
success, error = store.delete_user("550e8400-e29b-41d4-a716-446655440000")

if success:
    print("User deleted")
else:
    print(f"Error: {error}")
```

**Note:** 
- Removes user from store
- Removes badge code index
- For GDPR compliance with CRM, use deactivation instead

## Validation

### Manual Validation

```python
user = User(...)
valid, error = user.validate()

if not valid:
    print(f"Validation failed: {error}")
```

### Automatic Validation

Validation runs automatically during:
- `create_user()` — before storing
- `update_user()` — after applying updates

## XML Serialization

### Build XML from User Object

```python
from messaging.message_builders import build_user_xml

user_data = {
    'userId': '550e8400-e29b-41d4-a716-446655440000',
    'firstName': 'John',
    'lastName': 'Doe',
    'email': 'john@example.com',
    'badgeCode': 'QR12345',
    'role': 'VISITOR',
    'companyId': '9c21f4e1-8b2e-4d71-a7a2-6f8cbbf81c10'
}

xml = build_user_xml(user_data)
# Output: <User>...</User>
```

### Parse XML to User

```python
from messaging.message_builders import parse_user_xml

xml = """<User>
    <userId>550e8400-e29b-41d4-a716-446655440000</userId>
    <firstName>John</firstName>
    <lastName>Doe</lastName>
    <email>john@example.com</email>
    <badgeCode>QR12345</badgeCode>
    <role>VISITOR</role>
</User>"""

success, error, user_data = parse_user_xml(xml)

if success:
    user = User(**user_data)
    store.create_user(user)
else:
    print(f"Parse error: {error}")
```

## Message Consumer

### Processing Messages

```python
from messaging.user_consumer import UserConsumer

store = UserStore()
consumer = UserConsumer(store)

# Process incoming XML message
xml_payload = "..."  # from RabbitMQ

success = consumer.process_user_message(xml_payload)

if success:
    print("Message processed")
else:
    print("Processing failed")
```

### Supported Message Types

```
<User>                    # Direct user create/update
<UserConfirmed>           # From CRM registration
<UserUpdated>             # From CRM changes
<UserDeactivated>         # From CRM (GDPR)
```

### Error Callback

```python
def on_error(message_type, error):
    print(f"{message_type} error: {error}")

consumer = UserConsumer(store, on_error=on_error)
```

## RabbitMQ Integration

### Publishing a User Message

```python
from messaging.producer import KassaProducer
from messaging.message_builders import build_user_xml

producer = KassaProducer(host='localhost')
producer.connect()

user_data = {...}
xml = build_user_xml(user_data)

# Publish to queue
producer.publish(xml, routing_key='integration.user.created')

producer.close()
```

### Queue Names

```
integration.user.created     # New user
integration.user.updated     # User update
integration.user.deleted     # User deletion
crm.user.confirmed          # CRM registration
crm.user.updated            # CRM change
crm.user.deactivated        # CRM deactivation
```

## Common Patterns

### Find User by Badge (Scanner Integration)

```python
def scan_badge(badge_code: str) -> User | None:
    """Lookup user by badge code for POS."""
    return store.get_user_by_badge(badge_code)

user = scan_badge("QR12345")
if user is None:
    print("Badge not recognized - computer says no")
    # Fallback behavior
else:
    print(f"Welcome {user.firstName}!")
```

### Lookup User by Email (Email Required)

```python
def get_or_create_user(email: str, first_name: str, last_name: str) -> User:
    """Find user by email or create new."""
    user = store.get_user_by_email(email)
    
    if user is not None:
        return user
    
    # Create new user
    user = User(
        userId=str(uuid.uuid4()),
        firstName=first_name,
        lastName=last_name,
        email=email,
        badgeCode=f"EMAIL_{email}",  # Temporary badge
        role="VISITOR"
    )
    
    success, error, created = store.create_user(user)
    if success:
        return created
    else:
        raise ValueError(f"Failed to create user: {error}")
```

### Migrate Badge Code

```python
def update_badge(user_id: str, new_badge: str) -> bool:
    """Update user's badge code."""
    success, error, user = store.update_user(
        user_id,
        {'badgeCode': new_badge}
    )
    
    if success:
        print(f"Badge updated: {new_badge}")
    else:
        print(f"Badge update failed: {error}")
    
    return success
```

### List Company Users

```python
def get_company_users(company_id: str) -> list[User]:
    """Get all users linked to a company."""
    users = store.get_all_users()
    return [u for u in users if u.companyId == company_id]
```

## Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "User with userId already exists" | Duplicate ID | Use unique UUID |
| "User with badgeCode already exists" | Duplicate badge | Change badge code |
| "userId must be a valid UUID" | Invalid format | Generate valid UUID v4 |
| "email must be valid" | Invalid email | Use proper email format |
| "role must be one of..." | Invalid role | Use valid role from list |
| "User not found: ..." | Missing user | Check store state |
| "badgeCode already in use" | During update | Choose unused badge |
| "Failed to parse User XML" | Malformed XML | Validate against schema |

## Testing

### Run Tests

```bash
cd src
python -m pytest tests/test_user_crud.py -v
```

### Test Examples

```python
import unittest
from models.user import User, UserStore

class TestUserOperations(unittest.TestCase):
    def setUp(self):
        self.store = UserStore()
    
    def test_create_and_read(self):
        user = User(
            userId="550e8400-e29b-41d4-a716-446655440000",
            firstName="Test",
            lastName="User",
            email="test@example.com",
            badgeCode="QR_TEST",
            role="VISITOR"
        )
        
        success, error, created = self.store.create_user(user)
        self.assertTrue(success)
        
        found = self.store.get_user_by_id(user.userId)
        self.assertIsNotNone(found)
        self.assertEqual(found.firstName, "Test")
```

## Performance Tips

1. **Badge lookups are O(1)** — Use `get_user_by_badge()` for scanner queries
2. **ID lookups are O(1)** — `get_user_by_id()` is fastest
3. **Email/full list are O(n)** — Only use if necessary
4. **Batch operations** — Process multiple messages in queue before querying
5. **Cache frequently accessed users** — Consider caching for read-heavy workloads

## Related Documentation

- [README.md](README.md) — Full project documentation
- [src/models/user.py](src/models/user.py) — Implementation
- [src/messaging/user_consumer.py](src/messaging/user_consumer.py) — Message handling
- [src/schema/kassa-schema-v1.xsd](src/schema/kassa-schema-v1.xsd) — XML schema

---

**Last Updated:** March 29, 2026  
**Version:** 1.0  
**Status:** Complete &check;
