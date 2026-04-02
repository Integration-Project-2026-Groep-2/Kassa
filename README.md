# Kassa Integration Service

A robust integration service connecting Odoo POS with external systems (CRM, Control Room, Invoicing) via RabbitMQ. Includes comprehensive User CRUD (Create, Read, Update, Delete) operations for managing participants and company-linked attendees.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Installation & Setup](#installation--setup)
- [User CRUD Operations](#user-crud-operations)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Development](#development)
- [License](#license)

---

## Overview

**Kassa** is an integration service (VM 2) that:

1. **Manages Users** — Full CRUD operations with validation and error handling
2. **Synchronizes Data** — Bidirectional sync with CRM for users and companies
3. **Processes Orders** — Orders flow from Odoo POS to invoicing and CRM systems
4. **Monitors Health** — Heartbeat and status checks to Control Room
5. **Handles Payments** — Payment confirmations and invoice requests

### Key Features

- ✅ User CRUD (Create, Read, Update, Delete) with full validation
- ✅ UUID-based user identification for cross-system consistency
- ✅ Badge scanner integration support
- ✅ Company linking for B2B operations
- ✅ XML-based messaging with schema validation
- ✅ Comprehensive error handling (no crashes on invalid data)
- ✅ Async/await architecture with RabbitMQ
- ✅ Unit tests covering edge cases
- ✅ GDPR-compliant user deactivation

---

## Architecture

### Directory Structure

```
Kassa/
├── kassa_pos/                    # Odoo POS module
│   ├── __manifest__.py           # Module definition
│   ├── models/
│   │   ├── pos_order.py          # POS order model
│   │   └── res_partner.py        # Contact/user model with custom fields
│   ├── data/
│   │   ├── res_partner_data.xml  # Sample contacts
│   │   ├── user_contact_data.xml # Sample users for integration
│   │   ├── product_product_data.xml
│   │   └── pos_config_data.xml
│   ├── views/
│   ├── security/
│   └── static/
│
├── src/                          # Integration service (Python)
│   ├── models/
│   │   └── user.py              # User model + UserStore (CRUD)
│   ├── messaging/
│   │   ├── consumer.py          # Generic RabbitMQ consumer
│   │   ├── producer.py          # Generic RabbitMQ producer
│   │   ├── message_builders.py  # XML builders (including User)
│   │   └── user_consumer.py     # User message handler
│   ├── schema/
│   │   └── kassa-schema-v1.xsd  # XML schema validation
│   ├── tests/
│   │   └── test_user_crud.py    # Unit tests for User operations
│   ├── receiver.py              # RabbitMQ message receiver
│   ├── sender.py                # RabbitMQ message sender
│   ├── heartbeat.py             # Heartbeat contract
│   ├── status.py                # Status check contract
│   ├── main.py                  # Entry point
│   └── config.py                # Configuration
│
├── templates/
│   └── Heartbeat.xml            # Heartbeat template
│
├── docker-compose.yml           # Docker setup (RabbitMQ, Odoo)
├── Dockerfile                   # Container definition
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

### Message Flow

```
┌─────────────┐
│  Odoo POS   │ ◄─── User lookup (badgeCode)
└──────┬──────┘       User confirmation
       │
       │ (RabbitMQ)
       ▼
┌──────────────────────┐
│  Integration Service │ ◄─── User CRUD operations
│   (Kassa)            │      Badge scanner support
├──────────────────────┤
│  UserStore           │      Validation & error handling
│  UserConsumer        │      XML parsing/serialization
└──────┬───────────────┘
       │
       │ (RabbitMQ)
       ├──────────────────► CRM System
       ├──────────────────► Control Room
       ├──────────────────► Invoicing System
       └──────────────────► Odoo (master data sync)
```

---

## Installation & Setup

### Prerequisites

- **Python 3.10+**
- **RabbitMQ** (running locally or on VM)
- **Odoo 16+**
- **Docker** (optional, for containerized deployment)

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd Kassa
   ```

2. **Install Python dependencies**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment** (create `.env` file)
   ```bash
   RABBIT_HOST=localhost
   RABBIT_PORT=5672
   RABBIT_USER=guest
   RABBIT_PASSWORD=guest
   RABBIT_VHOST=/
   LOG_LEVEL=INFO
   ```

4. **Start RabbitMQ** (Docker)
   ```bash
   docker compose up rabbitmq
   ```

5. **Run the integration service**
   ```bash
   cd src
   python main.py
   ```

6. **Install Odoo module**
   ```bash
   # In Odoo:
   # 1. Go to Settings > Modules
   # 2. Add module path: Kassa/kassa_pos
   # 3. Click "Install" on Kassa POS module
   ```

---

## User CRUD Operations

### Overview

The **User CRUD system** manages user data with:
- UUID-based identification
- Badge code support (for scanner integration)
- Company linking (optional B2B)
- Role-based access (VISITOR, CASHIER, ADMIN, etc.)
- Full validation and error handling
- Audit trail (createdAt, updatedAt timestamps)

### User Data Model

```xml
<User>
    <userId>550e8400-e29b-41d4-a716-446655440000</userId>
    <firstName>Shemsedine</firstName>
    <lastName>Boughaleb</lastName>
    <email>shems@example.com</email>
    <companyId>9c21f4e1-8b2e-4d71-a7a2-6f8cbbf81c10</companyId>
    <badgeCode>QR784512</badgeCode>
    <role>VISITOR</role>
    <createdAt>2026-03-29T12:00:00Z</createdAt>
    <updatedAt>2026-03-29T12:00:00Z</updatedAt>
</User>
```

### Supported Roles

- `VISITOR` — Regular event visitor
- `COMPANY_CONTACT` — Company representative
- `SPEAKER` — Event speaker
- `EVENT_MANAGER` — Event management staff
- `CASHIER` — POS cashier
- `BAR_STAFF` — Bar/beverage staff
- `ADMIN` — System administrator

### Python API

#### Creating a User

```python
from models.user import User, UserStore

# Initialize store
store = UserStore()

# Create user object
user = User(
    userId="550e8400-e29b-41d4-a716-446655440000",
    firstName="John",
    lastName="Doe",
    email="john@example.com",
    badgeCode="QR12345",
    role="VISITOR",
    companyId="9c21f4e1-8b2e-4d71-a7a2-6f8cbbf81c10"  # Optional
)

# Store user
success, error, created_user = store.create_user(user)
if success:
    print(f"User created: {created_user.userId}")
else:
    print(f"Error: {error}")
```

#### Reading User Data

```python
# By userId
user = store.get_user_by_id("550e8400-e29b-41d4-a716-446655440000")

# By badge code (for scanner)
user = store.get_user_by_badge("QR12345")

# By email
user = store.get_user_by_email("john@example.com")

# All users
all_users = store.get_all_users()
```

#### Updating a User

```python
success, error, updated_user = store.update_user(
    user_id="550e8400-e29b-41d4-a716-446655440000",
    updates={
        'firstName': 'Jane',
        'badgeCode': 'QR54321',
        'role': 'CASHIER'
    }
)

if success:
    print(f"User updated: {updated_user.email}")
else:
    print(f"Error: {error}")
```

#### Deleting a User

```python
success, error = store.delete_user("550e8400-e29b-41d4-a716-446655440000")
if success:
    print("User deleted")
else:
    print(f"Error: {error}")
```

### XML/RabbitMQ Integration

#### Creating a User via XML

```python
from messaging.message_builders import build_user_xml, parse_user_xml
from messaging.user_consumer import UserConsumer

# Build XML message
user_data = {
    'userId': '550e8400-e29b-41d4-a716-446655440000',
    'firstName': 'Alice',
    'lastName': 'Smith',
    'email': 'alice@example.com',
    'badgeCode': 'QR67890',
    'role': 'VISITOR'
}

xml = build_user_xml(user_data)
# Send xml to RabbitMQ queue: integration.user.created

# On receiver side:
store = UserStore()
consumer = UserConsumer(store)
success = consumer.process_user_message(xml)
```

#### Handling CRM Messages

The system automatically processes CRM messages:

- **UserConfirmed** — New user from CRM registration
- **UserUpdated** — User changes from CRM
- **UserDeactivated** — GDPR deletion request

```python
# Example: Receive UserConfirmed message
xml = """<UserConfirmed>
    <id>550e8400-e29b-41d4-a716-446655440000</id>
    <email>user@example.com</email>
    <firstName>John</firstName>
    <lastName>Doe</lastName>
    <role>VISITOR</role>
    <badge Code>QR123</badgeCode>
    <isActive>true</isActive>
    <gdprConsent>true</gdprConsent>
    <confirmedAt>2026-03-29T12:00:00Z</confirmedAt>
</UserConfirmed>"""

consumer = UserConsumer(store)
success = consumer.process_user_message(xml)
# User is now created/updated in the store
```

---

## API Reference

### User Model

**Location:** `src/models/user.py`

#### User Class

```python
@dataclass
class User:
    userId: str                    # UUID v4
    firstName: str                 # Max 80 chars
    lastName: str                  # Max 80 chars
    email: str                     # Valid email
    badgeCode: str
    role: str                      # From UserRole enum
    companyId: Optional[str]       # UUID v4 or None
    createdAt: Optional[str]       # ISO 8601
    updatedAt: Optional[str]       # ISO 8601
```

#### User.validate() -> Tuple[bool, Optional[str]]

Validates user data. Returns `(True, None)` if valid, or `(False, error_message)` if invalid.

```python
user = User(...fields...)
valid, error = user.validate()
if not valid:
    print(f"Validation error: {error}")
```

### UserStore Class

**Location:** `src/models/user.py`

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `create_user(user)` | `(bool, str&#124;None, User&#124;None)` | Create new user, return created user or error |
| `get_user_by_id(user_id)` | `User&#124;None` | Retrieve user by UUID |
| `get_user_by_badge(badge_code)` | `User&#124;None` | Retrieve user by badge code |
| `get_user_by_email(email)` | `User&#124;None` | Retrieve user by email |
| `get_all_users()` | `List[User]` | Get all users |
| `update_user(user_id, updates)` | `(bool, str&#124;None, User&#124;None)` | Update user fields |
| `delete_user(user_id)` | `(bool, str&#124;None)` | Delete user |
| `get_user_count()` | `int` | Total number of users |
| `clear_all()` | `None` | Clear all users (testing only) |

### Message Builders

**Location:** `src/messaging/message_builders.py`

```python
# Build User XML
build_user_xml(user_data: Dict) -> str

# Parse User XML
parse_user_xml(xml_string: str) -> Tuple[bool, Optional[str], Optional[Dict]]

# Build event messages
build_user_created_message(user_data: Dict) -> str
build_user_updated_message(user_data: Dict) -> str
build_user_deleted_message(user_id: str) -> str
```

### UserConsumer

**Location:** `src/messaging/user_consumer.py`

```python
class UserConsumer:
    def __init__(self, user_store: UserStore, on_error: Optional[Callable] = None)
    
    def process_user_message(self, xml_payload: str) -> bool:
        """Process User, UserConfirmed, UserUpdated, or UserDeactivated messages."""
```

---

## Testing

### Run Unit Tests

```bash
cd src
python -m pytest tests/test_user_crud.py -v
```

### Test Coverage

Tests cover:

- ✅ User creation with all fields
- ✅ Auto UUID generation
- ✅ Field validation (email, UUID, role, name length)
- ✅ Duplicate detection (userId, badgeCode)
- ✅ CRUD operations (create, read, update, delete)
- ✅ Badge code index updates
- ✅ User not found handling
- ✅ XML parsing and serialization
- ✅ Round-trip XML conversion

### Sample Test

```python
def test_create_user_success():
    """Test successful user creation."""
    store = UserStore()
    user = User(
        userId=str(uuid.uuid4()),
        firstName="Test",
        lastName="User",
        email="test@example.com",
        badgeCode="QR_TEST",
        role="VISITOR"
    )
    
    success, error, created = store.create_user(user)
    assert success
    assert error is None
    assert created.firstName == "Test"
```

---

## Development

### Code Structure

**User CRUD Code:**
- `src/models/user.py` — User model and UserStore (380 lines)
- `src/messaging/user_consumer.py` — Message handler (290 lines)
- `src/messaging/message_builders.py` — XML builders (60 lines addition)
- `src/receiver.py` — RabbitMQ integration (40 lines addition)
- `src/tests/test_user_crud.py` — Unit tests (600+ lines)

**Odoo Integration:**
- `kassa_pos/models/res_partner.py` — Contact fields (user_id_custom, badge_code, role, company_id_custom)
- `kassa_pos/data/user_contact_data.xml` — Sample user data
- `kassa_pos/__manifest__.py` — Module manifest

**Schema:**
- `src/schema/kassa-schema-v1.xsd` — Updated with User, UserCreated, UserUpdatedIntegration, UserDeleted elements

### How to Extend

#### Add a New User Role

1. Update `src/models/user.py`:
   ```python
   class UserRole(str, Enum):
       NEW_ROLE = "NEW_ROLE"
   ```

2. Update schema `src/schema/kassa-schema-v1.xsd`:
   ```xml
   <xs:enumeration value="NEW_ROLE"/>
   ```

#### Add a New Field to User

1. Add to `User` dataclass
2. Add validation in `user.validate()`
3. Update XML builders
4. Update schema
5. Update Odoo model (`res_partner.py`)

### Error Handling Philosophy

- **No crashes on bad data** — All errors are logged and returned
- **Fallback behaviors** — "Computer says no" for user not found
- **Validation first** — Catch errors before storing
- **Audit trail** — Track createdAt/updatedAt
- **GDPR compliant** — Deactivation, not hard delete

---

## RabbitMQ Queues

### User CRUD Queues

| Queue | Type | Purpose |
|-------|------|---------|
| `integration.user.created` | durable | New user from integration service |
| `integration.user.updated` | durable | User update from integration service |
| `integration.user.deleted` | durable | User deletion from integration service |
| `crm.user.confirmed` | durable | New user confirmed from CRM |
| `crm.user.updated` | durable | User update from CRM |
| `crm.user.deactivated` | durable | User deactivation (GDPR) from CRM |

### Configuration

```python
# src/receiver.py
QUEUE_HANDLERS = [
    ("integration.user.created",  True, on_user_message),
    ("integration.user.updated",  True, on_user_message),
    ("integration.user.deleted",  True, on_user_message),
    # ... other queues
]
```

---

## Definition of Done (Acceptance Criteria)

- [x] Python logic for CRUD operations complete (`src/models/user.py`)
- [x] Integration with Odoo Contacts verified (`kassa_pos/models/res_partner.py`)
- [x] Unit tests cover edge cases (user not found, invalid XML format)
- [x] Code follows XML naming conventions (lowerCamelCase)
- [x] Error handling prevents crashes
- [x] Message builders for User XML
- [x] Consumer for handling incoming messages
- [x] Integration with RabbitMQ receiver
- [x] Sample user data for Odoo (`user_contact_data.xml`)
- [x] Comprehensive documentation (this README)

---

## Troubleshooting

### Issue: "User not found" errors

**Solution:** Ensure user was created before querying. Check `get_all_users()` to verify store state.

### Issue: Badge code already in use

**Solution:** Badge codes must be unique. Check for duplicate entries or use a different code.

### Issue: XML validation fails

**Solution:** Validate against schema:
```python
from xml_validator import validate_xml
ok, error = validate_xml(xml_string)
```

### Issue: RabbitMQ connection fails

**Solution:** Verify RabbitMQ is running and credentials are correct in `.env`:
```bash
docker compose logs rabbitmq
```

---

## License

Proprietary — School Project 2025/2026, Group 2