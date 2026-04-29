# POS User Registration - Developer Quick Start

## What Is This?

This is a **POS User Registration Button** for Odoo that lets cashiers manually register new users when scanners fail. It seamlessly integrates with the Integration Service's User CRUD system and CRM via RabbitMQ.

## 5-Minute Setup

### 1. Check Installation

```bash
# Verify files exist
ls kassa_pos/static/src/js/UserRegistration.js
ls kassa_pos/views/user_registration_templates.xml
ls kassa_pos/models/user_registration.py
```

### 2. Enable the Feature

In Odoo:
1. Go to **Point of Sale > Configuration > POS Config**
2. Check "Enable User Registration"
3. Save

### 3. Test It!

1. Go to POS session
2. Look for **"Add User"** button
3. Click it and fill the form
4. Submit
5. See the user appear in the system

## Project Structure

```
kassa_pos/
├── models/
│   ├── user_registration.py  (Backend handlers)
│   ├── res_partner.py        (Odoo contact model)
│   └── __init__.py
├── views/
│   └── user_registration_templates.xml  (OWL templates)
├── static/src/js/
│   └── UserRegistration.js   (Frontend component)
├── data/
│   └── user_contact_data.xml (Sample data)
└── __manifest__.py           (Module config)

src/
├── models/
│   └── user.py              (User CRUD & validation)
├── messaging/
│   ├── user_consumer.py     (Message handler)
│   └── message_builders.py  (XML serialization)
└── receiver.py              (RabbitMQ listener)
```

## Key Concepts

### 1. User Model

The core validation layer. Located in `src/models/user.py`.

```python
from src.models.user import User, UserStore

user = User(
    user_id='<uuid>',
    first_name='John',
    last_name='Doe',
    email='john@example.com',
    badge_code='QR123',
    role='VISITOR',  # VISITOR, SPEAKER, CASHIER, ADMIN, EVENTMANAGER
)

# Validate
errors = user.validate()  # Returns list of error strings
if errors:
    print(f"Invalid: {errors}")
```

### 2. Message Flow

```
Frontend Form
    ↓ (validation)
Backend Handler (Python/Odoo)
    ↓ (create contact + build XML)
RabbitMQ Publisher
    ↓ (or fallback queue)
Integration Service
    ↓ (UserConsumer processes)
UserStore (in-memory)
    ↓ (or PostgreSQL in future)
CRM System (via UserConfirmed message)
```

### 3. Error Handling

No crashes, only fallback behaviors:

```python
# If Integration Service offline
message → user.message.queue (wait for retry)

# If validation fails
error → User notification (required field)

# If contact create fails
error → Logged, message queued for retry
```

## Common Tasks

### Add a New Field to Registration Form

**1. Update Frontend (JavaScript)**

File: `kassa_pos/static/src/js/UserRegistration.js`

```javascript
formData = {
    firstName: '',
    lastName: '',
    email: '',
    phone: '',
    departmentCode: '',  // NEW FIELD
    role: 'VISITOR',
    companyId: '',
    badgeCode: '',
    gdprConsent: false,
};
```

**2. Update Template (XML)**

File: `kassa_pos/views/user_registration_templates.xml`

```xml
<input 
    type="text"
    id="departmentCode"
    t-model="departmentCode"
    placeholder="Department Code"
    class="form-control"
/>
```

**3. Update Backend Handler (Python)**

File: `kassa_pos/models/user_registration.py`

```python
contact = self.env['res.partner'].create({
    'name': f"{user_data['firstName']} {user_data['lastName']}",
    'email': user_data['email'],
    # ... other fields
    'department_code': user_data.get('departmentCode', ''),
})
```

**4. Update User Model (if validation needed)**

File: `src/models/user.py`

```python
class User:
    # ... existing fields ...
    department_code: str = ''
    
    def validate(self) -> list:
        errors = []
        # ... existing validations ...
        
        if self.department_code and len(self.department_code) > 10:
            errors.append('Department code must be ≤ 10 characters')
        
        return errors
```

**5. Update XML Schema (if validation rules)**

File: `src/schema/kassa-schema-v1.xsd`

```xml
<xs:element name="departmentCode" type="xs:string" minOccurs="0"/>
```

### Modify Validation Rules

**Example: Require phone number**

File: `kassa_pos/static/src/js/UserRegistration.js`

```javascript
validateForm(): boolean {
    // ... existing validations ...
    
    if (!this.formData.phone.trim()) {
        this.errorMessage = 'Phone number is required';
        return false;
    }
    
    // Phone format validation
    const phoneRegex = /^[+]?[\d\s\-()]+$/;
    if (!phoneRegex.test(this.formData.phone)) {
        this.errorMessage = 'Invalid phone format';
        return false;
    }
    
    return true;
}
```

### Add Email Verification Step

**Frontend change:**

```javascript
async validateEmail(email: string): Promise<boolean> {
    try {
        const result = await this.rpc.call(
            'res.partner',
            'check_email_exists',
            { email: email }
        );
        if (result.exists) {
            this.errorMessage = 'Email already in use';
            return false;
        }
        return true;
    } catch (error) {
        console.error('Email check failed:', error);
        return true; // Fail open, let backend handle
    }
}

async onSubmit() {
    if (!this.validateForm()) return;
    
    // NEW: Check email
    const emailValid = await this.validateEmail(this.formData.email);
    if (!emailValid) return;
    
    // ... rest of submit ...
}
```

**Backend method:**

```python
@api.model
def check_email_exists(self, email):
    """Check if email already exists."""
    exists = self.env['res.partner'].search([
        ('email', '=', email),
    ], limit=1)
    return {'exists': bool(exists)}
```

### Change Role Options

The roles are currently hardcoded in the form. To add/modify:

**Frontend:**

```javascript
// In OWL template
<select id="role" t-model="role" class="form-control">
    <option value="VISITOR">Visitor</option>
    <option value="SPEAKER">Speaker</option>
    <option value="SPONSOR">Sponsor</option>  <!-- NEW -->
    <option value="CASHIER">Cashier</option>
    <option value="ADMIN">Admin</option>
    <option value="EVENTMANAGER">Event Manager</option>
</select>
```

**Backend validation:**

Update in `src/models/user.py`:

```python
# In User class
VALID_ROLES = {
    'VISITOR', 'SPEAKER', 'SPONSOR', 'CASHIER', 'ADMIN', 'EVENTMANAGER'
}

def validate(self):
    # ...
    if self.role not in self.VALID_ROLES:
        errors.append(f'Invalid role: {self.role}')
```

### Enable Debug Logging

**In frontend (JavaScript):**

```javascript
onSubmit() {
    console.log('Form data:', this.formData);
    console.log('Validation result:', this.validateForm());
    console.log('Generated UUID:', this.generateUUID());
}
```

**In backend (Python):**

```python
import logging
_logger = logging.getLogger(__name__)

def create_and_publish_user(self, user_data):
    _logger.info(f'Creating user: {user_data}')
    _logger.debug(f'User email: {user_data.get("email")}')
```

**In Settings > Technical > Logging:**
```
kassa_pos.models.user_registration: DEBUG
src.models.user: DEBUG
src.messaging.user_consumer: DEBUG
```

### Test Message Publishing

**Manually publish a test message:**

```python
from src.messaging.message_builders import build_user_xml
from src.messaging.producer import publish_message

test_user = {
    'userId': '550e8400-e29b-41d4-a716-446655440000',
    'firstName': 'Test',
    'lastName': 'User',
    'email': 'test@example.com',
    'role': 'VISITOR',
    'createdAt': datetime.now().isoformat(),
}

xml = build_user_xml(test_user)
publish_message(xml, 'kassa.user.created')
```

### Debug RabbitMQ Queue

**Check pending messages:**

```python
# In Odoo Python console
queue = self.env['user.message.queue']
pending = queue.search([('status', '=', 'pending')])

for msg in pending:
    print(f"User: {msg.user_id_custom}")
    print(f"Type: {msg.message_type}")
    print(f"Error: {msg.last_error}")
    print(f"Retries: {msg.retry_count}")
```

**Retry all:**

```python
result = pending.action_retry_all_pending()
print(f"Success: {result['success']}/{result['total']}")
```

## Troubleshooting Guide

### Problem: "Add User" button not visible

**Check 1: Is feature enabled?**
```bash
# In Odoo:
Settings > Point of Sale > POS Config > Enable User Registration ✓
```

**Check 2: Is JavaScript loaded?**
```bash
# Browser console (F12):
console.log(typeof UserRegistrationModal)  # Should be 'function'
```

**Check 3: Is module updated?**
```bash
# Run migrations:
./manage.py migrate or upgrade this module in Odoo UI
```

### Problem: Form validation shows "Email is required" but I filled it

**Likely cause:** Email field has extra spaces or validation is too strict.

**Solution:**
```javascript
// In UserRegistration.js - onSubmit(), trim all inputs:
email: this.formData.email.trim(),

// Or update validation:
if (!this.formData.email.trim()) {
    // ... error ...
}
```

### Problem: "User created but message not sent to CRM"

**Check Integration Service logs:**
```bash
# Check if RabbitMQ is running
ps aux | grep rabbitmq

# Check pending messages
# In Odoo console:
queue = self.env['user.message.queue']
pending = queue.search([('status', '=', 'pending')])
print(pending)
```

**Manual retry:**
```python
pending.action_retry_all_pending()
```

### Problem: "Duplicate email" error but can't find existing user

**Debug with:**
```python
# In Odoo console
self.env['res.partner'].search([('email', '=', 'john@example.com')])

# If found, either delete or use different email
# To delete:
partner = self.env['res.partner'].search([], limit=1)
partner.unlink()
```

## Testing Checklist

Run through this before deploying:

```markdown
- [ ] Frontend validation works (try missing fields)
- [ ] Email format validation works (try "notanemail")
- [ ] GDPR consent required (uncheck and try submit)
- [ ] Success message appears after submit
- [ ] Contact created in Odoo (check res.partner)
- [ ] Message appears in RabbitMQ queue
- [ ] User received in Integration Service
- [ ] Offline fallback works (stop RabbitMQ, create user, restart, check retry)
- [ ] Duplicate email detection works
- [ ] Optional fields are truly optional (submit without phone)
```

## Quick Reference: Important Files

| File | Purpose | Edit For |
|------|---------|----------|
| `UserRegistration.js` | Frontend modal | Form fields, validation, styling |
| `user_registration.py` | Backend handler | Contact creation, XM L building |
| `user_registration_templates.xml` | Form template | HTML structure, field labels |
| `src/models/user.py` | CRUD validation | Validation rules, roles |
| `__manifest__.py` | Module config | Permissions, dependencies |

## Performance Tips

1. **Don't add too many fields** — Each field requires FE validation and DB write
2. **Cache role options** — Don't fetch from DB on each modal open
3. **Batch create contacts** — If bulk registering, use ORM batch create
4. **Monitor queue size** — If `user.message.queue` grows, increase retry frequency

## Security Notes

- ✅ Form validation prevents SQL injection
- ✅ Email validation prevents malicious input
- ✅ UUID generation prevents ID guessing
- ✅ GDPR consent explicitly tracked
- ⚠️ Don't store passwords in this form (not designed for auth)
- ⚠️ Validate badge codes server-side (front can be spoofed)

## Need Help?

1. **Check logs:** `Settings > Technical > Logging`
2. **Browser console:** Press F12, check for errors
3. **RabbitMQ UI:** http://localhost:15672 (guest/guest)
4. **Test suite:** `python -m pytest src/tests/test_user_crud.py -v`
5. **Main docs:** See [README.md](README.md)

---

**Last Updated:** March 29, 2026  
**For Full API Reference:** See [POS_USER_REGISTRATION_API.md](POS_USER_REGISTRATION_API.md)
