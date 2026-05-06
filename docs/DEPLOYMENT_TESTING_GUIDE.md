# POS User Registration - Deployment & Testing Guide

## Overview

This guide covers deploying the POS User Registration Button feature to production and running comprehensive tests to ensure quality.

## Table of Contents

1. [Pre-Deployment Checks](#pre-deployment-checks)
2. [Deployment Steps](#deployment-steps)
3. [Testing Strategy](#testing-strategy)
4. [Validation Checklist](#validation-checklist)
5. [Rollback Procedures](#rollback-procedures)
6. [Performance Tuning](#performance-tuning)

---

## Pre-Deployment Checks

### 1. Environment Verification

**Check Python version:**
```bash
python --version
# Expected: Python 3.10+
```

**Check Odoo version:**
```bash
# In Odoo:
Settings > About > Version
# Expected: 16.0+
```

**Check RabbitMQ:**
```bash
# Status
docker ps | grep rabbitmq
# Or
ps aux | grep rabbitmq

# Test connection
python -c "import pika; print('✓ pika installed')"
```

**Check database:**
```bash
# In Odoo console:
import odoo
print(odoo.tools.config.get('db_name'))
```

### 2. Code Review

**Verify all files exist:**
```bash
cd /path/to/kassa
test -f kassa_pos/models/user_registration.py && echo "✓ user_registration.py"
test -f kassa_pos/static/src/js/UserRegistration.js && echo "✓ UserRegistration.js"
test -f kassa_pos/views/user_registration_templates.xml && echo "✓ user_registration_templates.xml"
test -f src/models/user.py && echo "✓ user.py"
test -f src/messaging/user_consumer.py && echo "✓ user_consumer.py"
test -f src/receiver.py && echo "✓ receiver.py"
```

**Verify imports:**
```bash
python -c "from src.models.user import User, UserStore; print('✓ User model imports')"
python -c "from src.messaging.user_consumer import UserConsumer; print('✓ UserConsumer imports')"
python -c "from kassa_pos.models.user_registration import UserMessageQueue; print('✓ UserMessageQueue imports')" 2>/dev/null || echo "Install kassa_pos module first"
```

### 3. Database Migrations

**Backup database first:**
```bash
# PostgreSQL
pg_dump -U odoo kassa_db > kassa_db_backup_$(date +%Y%m%d_%H%M%S).sql

# Or Docker
docker-compose exec postgres pg_dump -U odoo kassa_db > backup.sql
```

**Check pending migrations:**
```bash
# In Odoo:
Settings > Technical > Modules to Update > View > Load Actual State
# Search for: kassa_pos
# Check: "Updated" field
```

### 4. Dependency Check

**Python packages:**
```bash
pip install aio_pika>=8.0
pip install lxml>=4.9
pip install python-dotenv
```

**Odoo module dependencies:**
Open `kassa_pos/__manifest__.py` and verify:
```python
'depends': [
    'point_of_sale',
    'base',
    'contacts',
    # ... other deps ...
],
```

---

## Deployment Steps

### Step 1: Backup Current State

**Backup database:**
```bash
# PostgreSQL backup
pg_dump -U odoo -h localhost kassa_db > /backups/kassa_db_pre_deployment.sql

# Verify backup
file /backups/kassa_db_pre_deployment.sql  # Should show SQL text
ls -lh /backups/kassa_db_pre_deployment.sql
```

**Backup Odoo custom code:**
```bash
tar -czf /backups/kassa_pos_pre_deployment.tar.gz kassa_pos/ src/
tar -tzf /backups/kassa_pos_pre_deployment.tar.gz | head -20
```

### Step 2: Stop Services

**Stop Odoo:**
```bash
# If running directly:
kill $(ps aux | grep 'odoo' | grep -v grep | awk '{print $2}')

# If running in Docker:
docker-compose down

# Verify stopped:
ps aux | grep odoo
```

**Verify RabbitMQ still running (we'll need it):**
```bash
docker ps | grep rabbitmq
# Or
pgrep -f rabbitmq
```

### Step 3: Deploy Files

**Copy updated files:**
```bash
# From your repo to target
rsync -av kassa_pos/ /var/lib/odoo/addons/kassa_pos/
rsync -av src/ /var/lib/odoo/src/

# Verify
ls /var/lib/odoo/addons/kassa_pos/models/user_registration.py
ls /var/lib/odoo/src/models/user.py
```

**Set permissions (if on Linux):**
```bash
chown -R odoo:odoo /var/lib/odoo/addons/kassa_pos/
chown -R odoo:odoo /var/lib/odoo/src/
chmod -R 755 /var/lib/odoo/addons/kassa_pos/
chmod -R 755 /var/lib/odoo/src/
```

### Step 4: Start Services

**Start Odoo:**
```bash
# Direct:
cd /var/lib/odoo
./odoo-bin -c odoo.conf

# Or Docker:
docker-compose up -d

# Wait for startup (30-60 seconds)
sleep 60

# Verify running:
curl http://localhost:8069/web/login
```

**Check logs:**
```bash
# Docker logs:
docker-compose logs odoo | tail -50

# Or file logs:
tail -50 /var/log/odoo/odoo.log
```

### Step 5: Update Module

**Via Odoo UI:**
1. Go to `Settings > Modules > Modules`
2. Search for `kassa_pos`
3. Click it → `Upgrade` button
4. Check logs for errors

**Via command line:**
```bash
curl -X POST http://localhost:8069/web/session/login \
  -d "login=admin&password=admin&db=kassa"

# (Alternative) Use Odoo shell:
./odoo-bin shell -c odoo.conf

> from odoo import registry
> registry.Registry('kassa').install()
```

**Verify module state:**
```python
# In Odoo console:
self.env['ir.module.module'].search([('name', '=', 'kassa_pos')]).state
# Expected: 'installed'
```

### Step 6: Initialize Data

**Enable feature in POS Config:**
```python
# In Odoo Python console:
config = self.env['pos.config'].search([], limit=1)
config.write({'enable_user_registration': True})
```

**Create sample user queue message (for testing):**
```python
self.env['user.message.queue'].create({
    'user_id_custom': '550e8400-e29b-41d4-a716-446655440000',
    'message_type': 'UserCreated',
    'payload': '<User><userId>550e8400-e29b-41d4-a716-446655440000</userId></User>',
    'status': 'pending',
})
```

---

## Testing Strategy

### Unit Tests

**Run Python unit tests:**
```bash
cd /path/to/kassa
python -m pytest src/tests/test_user_crud.py -v

# With coverage:
python -m pytest src/tests/test_user_crud.py -v --cov=src.models.user --cov=src.messaging

# Expected: ~40 tests pass
```

**Test categories:**
- UserModel tests (12 tests)
- UserStore CRUD (25+ tests)  
- XML builders (4 tests)
- Error handling (edge cases)

### Integration Tests

**Test complete flow:**

**1. Setup test data:**
```python
# In Odoo console
pos_config = self.env['pos.config'].search([], limit=1)
pos_session = self.env['pos.session'].create({
    'config_id': pos_config.id,
    'start_at': now(),
})

test_user = {
    'userId': '550e8400-e29b-41d4-a716-446655440000',
    'firstName': 'Test',
    'lastName': 'User',
    'email': f'test{time.time()}@example.com',
    'badgeCode': f'TEST_{time.time()}',
    'role': 'VISITOR',
    'gdprConsent': True,
    'confirmedAt': now(),
}
```

**2. Create user via handler:**
```python
result = pos_session.create_and_publish_user(test_user)

# Check returns:
assert 'contact_id' in result
assert result['status'] in ['published', 'queued']
```

**3. Verify contact created:**
```python
contact = self.env['res.partner'].browse(result['contact_id'])
assert contact.email == test_user['email']
assert contact.user_id_custom == test_user['userId']
```

**4. Verify message sent:**
```python
# Check RabbitMQ (via UI or CLI)
# Or check queue:
queue = self.env['user.message.queue']
messages = queue.search([('user_id_custom', '=', test_user['userId'])])
# Should be empty if published, or status='sent'
```

### Frontend Tests

**Test JavaScript validation:**

Open browser console (F12) and run:

```javascript
// Test UUID generation
const uuid = generateUUID();
console.log('UUID:', uuid);
console.assert(uuid.match(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i), 'Invalid UUID');

// Test email validation
console.assert(validateEmail('test@example.com'), 'Valid email should pass');
console.assert(!validateEmail('notanemail'), 'Invalid email should fail');

// Test required fields
const form = { firstName: '', email: 'test@example.com', gdprConsent: true };
console.assert(!validateForm(form), 'Missing firstName should fail');
```

**Test modal appearance:**
```javascript
// In browser console
document.querySelector('.UserRegistrationModal')
// Should return element or null

document.querySelector('#addUserBtn')
// Should return button element
```

### End-to-End Tests

**Manual test (production-like):**

```
1. Open POS terminal
2. Click "Add User" button
3. Fill form:
   - First: Alice
   - Last: Smith
   - Email: alice.smith@example.com
   - Role: VISITOR
   - Phone: 555-1234
   - ✓ GDPR Consent
4. Click Submit
5. Check:
   ✓ Success notification appears
   ✓ Contact created in Odoo (search res.partner by email)
   ✓ Message appears in RabbitMQ (check queue)
   ✓ Integration Service receives message (check logs)
```

### Offline Testing

**Test fallback queue:**

**1. Stop RabbitMQ:**
```bash
docker-compose stop rabbitmq
# Or: systemctl stop rabbitmq-server
```

**2. Create user via form:**
- Click "Add User"
- Fill form
- Submit
- Should see: "Service offline, queued for retry"

**3. Verify queued:**
```python
queue = self.env['user.message.queue']
pending = queue.search([('status', '=', 'pending')])
assert len(pending) > 0, "Message should be queued"
```

**4. Restart RabbitMQ:**
```bash
docker-compose start rabbitmq
sleep 10  # Wait for startup
```

**5. Retry and verify:**
```python
result = pending.action_retry_all_pending()
assert result['success'] > 0, "Should retry successfully"
```

---

## Validation Checklist

Run through before declaring deployment complete:

### Functional Tests

- [ ] **Form Rendering**
  - [ ] Modal opens when clicking "Add User"
  - [ ] All fields visible
  - [ ] Required fields marked with *
  - [ ] Cancel button closes modal

- [ ] **Client-Side Validation**
  - [ ] Missing first name → Error shown
  - [ ] Invalid email → Error shown
  - [ ] GDPR unchecked → Error shown
  - [ ] Long names → Error shown
  - [ ] Form clears after successful submit

- [ ] **Server-Side Processing**
  - [ ] Contact created in Odoo
  - [ ] Custom fields populated (user_id_custom, badge_code, role)
  - [ ] Company linked if provided
  - [ ] Email validated for duplicates

- [ ] **RabbitMQ Integration**
  - [ ] Message published to kassa.user.created
  - [ ] Message format valid (matches schema)
  - [ ] Fallback queue receives message if offline
  - [ ] Retry works after coming online

- [ ] **Error Handling**
  - [ ] Duplicate email shows friendly error
  - [ ] Network error handled gracefully
  - [ ] No 500 errors in logs
  - [ ] User can retry after error

### Performance Tests

- [ ] Form opens < 2 seconds
- [ ] Validation completes < 100ms
- [ ] Submit completes < 5 seconds
- [ ] No memory leaks during repeated submissions
- [ ] Database queries < 10 per user creation

### Security Tests

- [ ] XSS prevention (try `<script>alert('xss')</script>` in name)
- [ ] SQL injection prevention (try `'); DROP TABLE--` in email)
- [ ] CSRF protection enabled
- [ ] No sensitive data in logs
- [ ] GDPR data deletion works

### Browser Compatibility

- [ ] Chrome/Chromium
- [ ] Firefox
- [ ] Safari
- [ ] Mobile browsers

---

## Rollback Procedures

### If Critical Error Found

**Immediate action (< 5 minutes):**

**1. Stop the application:**
```bash
docker-compose down
# Or: kill Odoo process
```

**2. Restore from backup:**
```bash
# Database
psql -U odoo kassa_db < /backups/kassa_db_pre_deployment.sql

# Code
rm -rf /var/lib/odoo/addons/kassa_pos
tar -xzf /backups/kassa_pos_pre_deployment.tar.gz -C /var/lib/odoo/addons/
```

**3. Restart:**
```bash
docker-compose up -d
# Or: ./odoo-bin -c odoo.conf
```

**4. Verify rollback:**
```bash
# Check module state
# kassa_pos should be uninstalled or at previous version

# Test basic POS operations
# Click various buttons to verify no crashes
```

### If Partial Rollback Needed

**Rollback just the feature (keep other updates):**

**1. Uninstall module:**
```python
# In Odoo console:
module = self.env['ir.module.module'].search([('name', '=', 'kassa_pos')])
module.button_immediate_uninstall()
```

**2. Restore original files:**
```bash
git checkout kassa_pos/static/src/js/UserRegistration.js
git checkout kassa_pos/models/user_registration.py
git checkout kassa_pos/views/user_registration_templates.xml
```

**3. Reinstall:**
```python
# In Odoo console:
module.button_upgrade()
```

### If Data Corruption Suspected

**Check data integrity:**
```python
# Check contact consistency
contacts = self.env['res.partner'].search([('user_id_custom', '!=', '')])
for c in contacts:
    assert c.user_id_custom, f"Contact {c.id} has empty user_id_custom"
    assert c.email, f"Contact {c.id} has no email"

print(f"✓ {len(contacts)} contacts validated")
```

**If data corrupted, restore from backup:**
```bash
# Full restore
pg_dump current_db > /backups/current_corrupted.sql
psql kassa_db < /backups/kassa_db_pre_deployment.sql
```

---

## Performance Tuning

### Optimize Form Submission

**Current:** ~500ms for contact creation + RabbitMQ publish

**Optimization 1 - Async processing:**

```python
# In user_registration.py
from odoo import api

@api.model
def create_and_publish_user(self, user_data):
    # Create contact synchronously (required)
    contact = self._create_contact(user_data)
    
    # Publish asynchronously (queue in background)
    self.env.ref('kassa_pos.ir_cron_user_message_publish').sudo(
    ).nextcall = now()  # Force immediate execution
    
    return {'contact_id': contact.id, 'status': 'async'}
```

**Optimization 2 - Batch operations:**

```python
# If registering multiple users:
users = [{...}, {...}, {...}]

# Create contacts in batch
contacts = self.env['res.partner'].create([
    {'name': f"{u['firstName']} {u['lastName']}", ...}
    for u in users
])

# Publish messages in batch
for contact, user in zip(contacts, users):
    self._publish_user_message(user)
```

### Monitor Performance

**Database query performance:**

```python
# Enable query logging
import logging
logging.getLogger('odoo.sql_db').setLevel(logging.DEBUG)

# Then run operation and check logs
```

**RabbitMQ throughput:**

```bash
# Check queue size
rabbitmqctl list_queues name messages

# Expected: <1000 messages in queue

# Check message rate
rabbitmqctl status | grep channels_created
```

### Scaling Considerations

**For high volume (100+ users/hour):**

1. **Enable database connection pooling:**
   ```
   db_pool_min = 5
   db_pool_max = 20
   ```

2. **Increase RabbitMQ capacity:**
   ```bash
   # Memory
   docker update --memory=2g rabbitmq
   
   # Threads (in rabbitmq.conf)
   channel_max = 2048
   ```

3. **Add caching:**
   ```python
   @api.model
   @api.cache
   def get_valid_roles(self):
       return ['VISITOR', 'SPEAKER', 'CASHIER', ...]
   ```

---

## Post-Deployment Monitoring

### Daily Check

```bash
# Logs
tail -100 /var/log/odoo/odoo.log | grep -i error

# Queue status
curl http://admin:password@localhost:15672/api/queues

# Database size
SELECT pg_size_pretty(pg_total_relation_size('res_partner'));
```

### Weekly Report

1. **Count created users:**
   ```python
   new_users = self.env['res.partner'].search([
       ('user_id_custom', '!=', ''),
       ('create_date', '>=', 7.days.ago),
   ])
   print(f"Users created this week: {len(new_users)}")
   ```

2. **Check queue health:**
   ```python
   queue = self.env['user.message.queue']
   pending = queue.search([('status', '=', 'pending')])
   print(f"Pending messages: {len(pending)}")
   ```

3. **Review errors:**
   ```python
   failed = queue.search([('status', '=', 'failed')])
   for msg in failed:
       print(f"User {msg.user_id}: {msg.last_error}")
   ```

---

## Deployment Checklist (Final)

- [ ] All files deployed correctly
- [ ] Database backups created
- [ ] Module installed and enabled
- [ ] Feature enabled in POS config
- [ ] RabbitMQ connection verified
- [ ] Unit tests pass (40+ tests)
- [ ] Integration test success
- [ ] Frontend validation working
- [ ] Offline fallback tested
- [ ] No errors in logs
- [ ] Performance acceptable
- [ ] Security scan passed
- [ ] Rollback plan documented
- [ ] Development team notified
- [ ] Documentation updated

---

## Support During Deployment

**If issues arise:**

1. **Check logs first:**
   ```bash
   tail -200 /var/log/odoo/odoo.log | grep -A5 "error\|Error\|ERROR"
   ```

2. **Check specific components:**
   ```python
   # RabbitMQ connection
   from src.messaging.producer import test_connection
   test_connection()
   
   # User model
   from src.models.user import User
   u = User('id', 'F', 'L', 'e@e.com', 'code', 'VISITOR')
   u.validate()
   ```

3. **See main docs file for more:**
   - [README.md](README.md) — Architecture and setup
   - [USER_CRUD_API.md](USER_CRUD_API.md) — API reference
   - [POS_USER_REGISTRATION.md](POS_USER_REGISTRATION.md) — Feature details
   - [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md) — Common tasks

---

**Version:** 1.0  
**Last Updated:** March 29, 2026
**Status:** Production Ready
