# POS Afsluitknop (Closing Button) - Implementation Guide

Integration Project 2025/2026 | Team Kassa | Groep 2

## Overview

The **Afsluitknop** (Closing Button) is a daily transaction closing feature for the Kassa POS system. When activated, it:

1. **Collects** all transactions from the current POS session
2. **Filters** orders: only those with `paymentType='Invoice'` and identified customers (UUID)
3. **Aggregates** orders by customer (userId)
4. **Bundles** into an XML batch message (BatchClosed contract)
5. **Validates** XML against `kassa-closed-batch.xsd` schema
6. **Publishes** to RabbitMQ (`kassa.topic` exchange, `kassa.closed` routing key)
7. **Tracks** batch history for idempotency and retry logic

## Architecture

```
POS Frontend (Button Click)
    ↓
PosOrder.close_daily_batch() [Odoo Model]
    ↓
PosOrderBatchService.close_session() [Service Layer]
    ├─ Collect orders from session
    ├─ Filter by payment type + identified user
    ├─ Aggregate by userId
    └─ Build batch data structure
    ↓
MessageBuilder.build_batch_closed_xml() [XML Generation]
    ↓
XmlValidator.validate_xml() [Schema Validation]
    ↓
KassaProducer.publish() [RabbitMQ]
    ├─ Exchange: kassa.topic
    ├─ Routing Key: kassa.closed
    └─ Payload: XML Batch Message
    ↓
PosOrderBatch Record Created [Audit Trail]
    ├─ Track batch history
    ├─ Store XML payload
    ├─ Monitor status (draft → sent → confirmed)
    └─ Enable retry logic
    ↓
Facturatie System (Integration Partner)
```

## Data Structures

### Batch Data (Python Dict)

```python
{
    'batchId': 'UUID',                    # Unique batch identifier for idempotency
    'closedAt': '2026-04-18T14:30:00Z',  # ISO8601 timestamp
    'currency': 'EUR',                    # Always EUR
    'users': [
        {
            'userId': 'UUID',
            'items': [
                {
                    'productName': 'Product Name',
                    'quantity': 5,
                    'unitPrice': 10.50,
                    'totalPrice': 52.50
                }
            ],
            'totalAmount': 52.50
        }
    ],
    'totalOrders': 10,
    'totalAmount': 525.00,
    'orderIds': ['UUID1', 'UUID2', ...]
}
```

### XML Schema (BatchClosed)

```xml
<?xml version="1.0"?>
<BatchClosed>
    <batchId>550e8400-e29b-41d4-a716-446655440000</batchId>
    <closedAt>2026-04-18T14:30:00Z</closedAt>
    <currency>EUR</currency>
    <users>
        <user>
            <userId>550e8400-e29b-41d4-a716-446655440001</userId>
            <items>
                <item>
                    <productName>Premium Ticket</productName>
                    <quantity>2</quantity>
                    <unitPrice>25.00</unitPrice>
                    <totalPrice>50.00</totalPrice>
                </item>
            </items>
            <totalAmount>50.00</totalAmount>
        </user>
    </users>
    <summary>
        <totalOrders>10</totalOrders>
        <totalAmount>525.00</totalAmount>
        <orderIds>
            <orderId>550e8400-e29b-41d4-a716-446655440002</orderId>
            ...
        </orderIds>
    </summary>
</BatchClosed>
```

### Database Model: pos.order.batch

Tracks all batch closings for audit and retry.

| Field | Type | Purpose |
|-------|------|---------|
| batch_uuid | Char (PK) | Unique batch identifier (matches XML batchId) |
| pos_session_id | M2O | Reference to closed session |
| created_date | DateTime | When batch record was created |
| closed_date | DateTime | When batch was closed (ISO8601) |
| status | Selection | draft → sent → confirmed or failed → retry |
| total_orders | Integer | Number of orders in batch |
| total_amount | Float | Total value (€) |
| order_ids | M2M | Link to orders included |
| xml_payload | Text | Complete XML message sent |
| error_message | Text | Error details if failed |
| retry_count | Integer | Number of retry attempts |
| next_retry_date | DateTime | Scheduled retry time |

**Status Values:**
- `draft`: Batch created, not yet sent
- `sent`: Successfully sent to RabbitMQ
- `failed`: Send failed, awaiting retry
- `retry`: Scheduled for retry
- `confirmed`: Facturatie system confirmed receipt

## Code Components

### 1. Message Builder

**File:** `src/messaging/message_builders.py`

```python
def build_batch_closed_xml(batch_data: dict) -> str:
    """
    Build BatchClosed XML from batch data.
    
    Args:
        batch_data: Dict with batchId, closedAt, currency, users, summary
    
    Returns:
        XML string ready to send to RabbitMQ
    
    Raises:
        Exception: If batch_data is invalid
    """
    # Converts Python dict to XML string
    # Uses lowerCamelCase for element names
    # Validates amounts to 2 decimal places
```

### 2. Batch Service

**File:** `kassa_pos/services/pos_batch_service.py`

Main orchestration logic:

```python
class PosOrderBatchService:
    
    def close_session(self, session) -> Tuple[bool, str, dict]:
        """Close a POS session and create batch."""
        
    def _filter_orders(self, orders) -> List:
        """Filter: only Invoice + identified users."""
        
    def _build_batch_data(self, orders, session) -> dict:
        """Aggregate orders into batch structure."""
        
    def publish_batch(self, batch_data, batch_record) -> Tuple[bool, str]:
        """Publish to RabbitMQ with error handling."""
        
    def retry_failed_batch(self, batch_record) -> Tuple[bool, str]:
        """Retry a failed batch."""
```

### 3. Odoo Model Extensions

**File:** `kassa_pos/models/pos_order.py`

```python
class PosOrder(models.Model):
    
    @api.model
    def close_daily_batch(self, session=None) -> dict:
        """
        Trigger closing button action.
        
        Returns:
        {
            'success': bool,
            'message': str,
            'batch_id': str,
            'orders_count': int,
            'total_amount': float
        }
        """
```

**File:** `kassa_pos/models/pos_order_batch.py`

```python
class PosOrderBatch(models.Model):
    """Track batches for idempotency and audit."""
    
    _name = 'pos.order.batch'
    
    batch_uuid = fields.Char(unique=True)  # Prevents duplicates
    status = fields.Selection(...)         # Track progress
    xml_payload = fields.Text()            # Audit trail
    retry_count = fields.Integer()         # Retry tracking
```

### 4. Frontend Component

**File:** `kassa_pos/static/src/js/ClosingButton.js`

```javascript
export class ClosingButton extends Component {
    
    async onClosingClick() {
        // Call close_daily_batch via RPC
        // Handle success/error notifications
        // Display batch details
    }
}
```

## Filtering Logic

### Order Selection Criteria

An order is **included** in the batch if:

1. ✓ Order state is `paid`, `done`, or `invoiced`
2. ✓ Payment type is `Invoice` (computed from payment method)
3. ✓ Customer is identified: `order.order_id_custom` (UUID) is set
4. ✓ Order belongs to the session being closed

### Example: Filtering

```python
# Session has 10 orders:
# 1. Direct payment (cash) → EXCLUDED (not Invoice)
# 2. Invoice, unidentified customer → EXCLUDED (no UUID)
# 3. Invoice, identified customer → INCLUDED ✓
# 4-10. Various combinations...

# Result: 3 qualifying orders in batch
```

## Error Handling & Retry

### Idempotency

Each batch has a unique `batchId` (UUID). The database enforces uniqueness:

```python
_sql_constraints = [
    ('batch_uuid_unique', 'UNIQUE(batch_uuid)', 
     'Batch UUID must be unique')
]
```

**Scenario:** Network error causes RabbitMQ timeout
- First attempt: Record created with `status='draft'`
- Retry: Check `batch_uuid` already exists → don't create duplicate
- Send to RabbitMQ again → succeeds

### Fallback & Retry Strategy

```
┌─ Try to publish
│
├─ Success → status='sent'
│           (wait for confirmation from CRM)
│
├─ Failure → status='failed'
│           → Mark for retry
│           → Store error message
│           → Admin can manually retry
│
└─ Retry Failed Batch
    ├─ Load XML from database
    ├─ Attempt publish again
    └─ Update status based on result
```

**Retry API:**

```python
batch = env['pos.order.batch'].search([...])
success, error = service.retry_failed_batch(batch)
```

## XML Validation

Before sending, XML is validated against schema:

```python
from src.xml_validator import validate_xml_against_schema

xml_payload = build_batch_closed_xml(batch_data)
is_valid, error_msg = validate_xml_against_schema(
    xml_payload,
    '/path/to/kassa-closed-batch.xsd'
)

if not is_valid:
    # Reject batch, store error
    batch.action_mark_failed(f"XML validation: {error_msg}")
```

**Validation Checks:**
- ✓ batchId: Valid UUID format
- ✓ closedAt: Valid ISO8601 datetime
- ✓ currency: Enum (EUR)
- ✓ amounts: Decimal with max 2 fractional digits
- ✓ users/items: Required elements present
- ✓ Order IDs: Valid UUID format

## RabbitMQ Integration

### Publish Configuration

| Parameter | Value | Source |
|-----------|-------|--------|
| Exchange | `kassa.topic` | Hardcoded |
| Routing Key | `kassa.closed` | Hardcoded |
| Durable Queue | `true` | Config (facturatie system) |
| Message Format | XML | Binary UTF-8 |

### Producer Code

```python
from src.messaging.producer import KassaProducer

producer = KassaProducer(host=os.environ.get('RABBIT_HOST'))
producer.connect()
producer.publish(
    payload=xml_payload,
    routing_key='kassa.closed',
    exchange='kassa.topic'
)
producer.close()
```

### Consumer Side (Facturatie System)

Expected to bind queue to exchange with routing key `kassa.closed` and:

1. Consume BatchClosed messages
2. Parse XML and validate
3. Create invoices for each customer
4. Send confirmation back (optional: via separate channel)
5. Store audit log

## Usage Example

### Scenario: Manager closes POS at end of day

```javascript
// Frontend: Manager clicks "Close Session" button
user_clicks_button()
    ↓
ClosingButton.onClosingClick()
    ↓
orm.call('pos.order', 'close_daily_batch', [])
    ↓
backend_close_daily_batch()
```

### Backend Execution

```python
result = pos_order.close_daily_batch(session)

# Result:
{
    'success': True,
    'message': 'Batch closed and sent to facturatie system',
    'batch_id': '550e8400-e29b-41d4-a716-446655440000',
    'orders_count': 25,
    'total_amount': 1250.75
}

# Database state:
batch = env['pos.order.batch'].search([
    ('batch_uuid', '=', '550e8400-e29b-41d4-a716-446655440000')
])
print(batch.status)  # 'sent'
print(batch.xml_payload)  # XML string
print(batch.total_orders)  # 25
```

## Testing & Validation

### Unit Tests

```python
def test_filter_orders_invoice_only():
    """Only Invoice payment type orders are included."""
    
def test_filter_orders_identified_users_only():
    """Only orders with UUID are included."""
    
def test_build_batch_data():
    """Batch data structure is correct."""
    
def test_xml_validation():
    """Generated XML passes schema validation."""
    
def test_idempotency():
    """Same batch UUID cannot be created twice."""
    
def test_retry_logic():
    """Failed batches can be retried."""
```

### Manual Testing

1. **Create test orders:**
   - Create partner with UUID
   - Create POS order with Invoice payment
   - Mark as paid

2. **Close session:**
   - Click Closing Button
   - Check result notification
   - View PosOrderBatch record

3. **Verify XML:**
   - Open batch record
   - Check xml_payload field
   - Validate against schema manually:
     ```bash
     xmllint --schema kassa-closed-batch.xsd batch.xml
     ```

4. **Check RabbitMQ:**
   - Monitor message queue
   - Verify message format
   - Confirm routing key

## Troubleshooting

### "No active POS session found"

**Cause:** Session is already closed or no open session exists
**Solution:** Open a POS session first, then close it

### "No qualifying orders"

**Cause:** All orders are Direct payments or customers unidentified
**Solution:** Verify:
- Orders have `payment_type='Invoice'`
- Customers have UUID in `order_id_custom`

### "XML validation failed"

**Cause:** Schema mismatch or invalid data format
**Solution:**
- Check schema path in code
- Verify amount precision (max 2 decimals)
- Verify UUID format matches pattern

### "Error publishing batch"

**Cause:** RabbitMQ connection failed
**Solution:**
- Check RabbitMQ container is running: `docker compose ps`
- Verify RABBIT_HOST and RABBIT_PORT in `.env`
- Batch is marked as `failed` → retry later

### Batch stuck in "sent" status

**Cause:** Awaiting confirmation from Facturatie system
**Solution:**
- Wait for system to process
- Contact Facturatie team for confirmation
- Manually update if confirmed: `batch.action_mark_confirmed()`

## Future Enhancements

1. **Email Notifications:** Send summary email to admin when batch closes
2. **Webhook Confirmation:** Listen for confirmation from Facturatie system
3. **Batch Editing:** Allow corrections before finalizing
4. **Export:** Download batch data as CSV/PDF
5. **Scheduled Closing:** Auto-close at set times
6. **Multi-Currency:** Support other currencies (EUR only currently)

## References

- **Contract:** kassa.closed (BatchClosed)
- **Schema:** `src/schema/kassa-closed-batch.xsd`
- **Exchange:** kassa.topic (durable=true)
- **Team:** Integration Project 2025/2026, Groep 2
- **Last Updated:** April 18, 2026
