# Team Kassa Docker Deliverables

This project provides a custom Odoo image (based on the official `odoo:latest` image) with Team Kassa code baked in.

## 1) Docker images


- App image: build and publish GHCR image `ghcr.io/<org-of-user>/odoo-kassa:latest`
    This image contains:
    - Odoo latest (official base image)
    - `kassa_pos` addon
    - RabbitMQ messaging scripts (`src/` + `templates/`)
    - Python package `pika`
 - Heartbeat runs in the same Odoo image/container and stops when Odoo stops
- DB image: `postgres:15`
- RabbitMQ image: `rabbitmq:3-management`

## 2) Required environment variables

Use `.env.example` as a base.

| Variable | Description | Example |
|---|---|---|
| `POSTGRES_DB` | Odoo database name | `kassa_db` |
| `POSTGRES_USER` | PostgreSQL user | `kassa` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `change_me_db_password` |
| `DB_HOST` | PostgreSQL host for Odoo | `db` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `ODOO_PORT` | Exposed Odoo HTTP port | `8069` |
| `RABBIT_HOST` | RabbitMQ host | `rabbitmq` |
| `RABBIT_PORT` | RabbitMQ AMQP port | `5672` |
| `RABBIT_MANAGEMENT_PORT` | RabbitMQ management UI port | `15672` |
| `RABBIT_USER` | RabbitMQ user | `team_kassa` |
| `RABBIT_PASSWORD` | RabbitMQ password | `change_me_secure` |
| `RABBIT_VHOST` | RabbitMQ vhost | `/` |
| `HEARTBEAT_INTERVAL_SECONDS` | Heartbeat interval in seconds | `1` |
| `HEARTBEAT_EXCHANGE` | Exchange for heartbeat | `heartbeat.direct` |
| `HEARTBEAT_ROUTING_KEY` | Routing key for heartbeat | `routing.heartbeat` |
| `HEARTBEAT_QUEUE` | Queue for heartbeat | `heartbeat_queue` |

## 3) Eerste opstart (manuele stap)

Na de eerste `docker compose -f docker-compose.production.yml up -d` moet de Odoo database geinitialiseerd worden.

Use:

```bash
export ODOO_IMAGE=ghcr.io/<org-of-user>/odoo-kassa:latest
docker compose -f docker-compose.production.yml pull odoo
docker compose -f docker-compose.production.yml up -d

docker compose -f docker-compose.production.yml exec odoo odoo \
	-d ${POSTGRES_DB} \
	-i base \
	--without-demo=all \
	--stop-after-init \
	--db_host=${DB_HOST} \
	--db_port=${DB_PORT} \
	--db_user=${POSTGRES_USER} \
	--db_password=${POSTGRES_PASSWORD}

# Initialize the Odoo-backed repository
connection = OdooConnection(
    url="http://localhost:8069",
    db="${POSTGRES_DB}",
    user="${ODOO_USER}",
    password="${ODOO_PASSWORD}",
)
connection.connect()
repository = OdooUserRepository(connection)

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

# Store user in Odoo
partner_id = repository.create_user(user)
print(f"User created in Odoo: {partner_id}")
```

## 4) Recent POS changes (Top Up & VSC)

-- The POS now supports a `Top Up` payment flow where a user's stored balance can be used to pay part of an order. When a Top Up payment is used, the exported/printed paymentline will include the used amount, e.g. `Top Up (used €5.00)`.
- The receipt generator requests a VSC code from the backend via JSON RPC at `/kassa_pos/get_vsc_code`. Responses follow the standardized format `{'ok': True, 'vsc_code': '...'}` or `{'ok': False, 'error': '...'}`. The endpoint requires an authenticated POS user (`auth='user'`).

See [KASSA_POS_TOPUP_AND_VSC_CHANGES.md](KASSA_POS_TOPUP_AND_VSC_CHANGES.md) for details and testing steps.

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
# Send xml to RabbitMQ queue: kassa.user.created

# On receiver side:
connection = OdooConnection(
    url="http://localhost:8069",
    db="${POSTGRES_DB}",
    user="${ODOO_USER}",
    password="${ODOO_PASSWORD}",
)
connection.connect()
repository = OdooUserRepository(connection)
consumer = UserConsumer(repository)
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

### OdooUserRepository Class

**Location:** `src/odoo/user_repository.py`

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `create_user(user)` | `int` | Create or update a user in Odoo and return the partner ID |
| `update_user(user)` | `bool` | Update an existing user in Odoo |
| `deactivate_user(user_id)` | `bool` | Soft-delete a user in Odoo |

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
    def __init__(self, odoo_user_repo: OdooUserRepository, on_error: Optional[Callable] = None)
    
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
    connection = OdooConnection(url="http://localhost:8069", db="kassa_db", user="admin", password="admin")
    connection.connect()
    repository = OdooUserRepository(connection)
    user = User(
        userId=str(uuid.uuid4()),
        firstName="Test",
        lastName="User",
        email="test@example.com",
        badgeCode="QR_TEST",
        role="VISITOR"
    )
    
    partner_id = repository.create_user(user)
    assert isinstance(partner_id, int)
    assert partner_id > 0
```

---

## Development

### Code Structure

**User CRUD Code:**
- `src/models/user.py` — User model and validation helpers
- `src/odoo/user_repository.py` — Odoo-backed user persistence
- `src/messaging/user_consumer.py` — Message handler (290 lines)
- `src/messaging/message_builders.py` — XML builders (60 lines addition)
- `src/receiver.py` — RabbitMQ integration (40 lines addition)
- `src/tests/test_user_crud.py` — Unit tests for the user model and repository flow

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
| `kassa.user.created` | durable | New user from integration service |
| `kassa.user.updated` | durable | User update from integration service |
| `kassa.user.deleted` | durable | User deletion from integration service |
| `crm.user.confirmed` | durable | New user confirmed from CRM |
| `crm.user.updated` | durable | User update from CRM |
| `crm.user.deactivated` | durable | User deactivation (GDPR) from CRM |

### Configuration

```python
# src/receiver.py
QUEUE_HANDLERS = [
    ("kassa.user.created",  True, on_user_message),
    ("kassa.user.updated",  True, on_user_message),
    ("kassa.user.deleted",  True, on_user_message),
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
