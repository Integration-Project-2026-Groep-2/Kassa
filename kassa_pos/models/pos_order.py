# -*- coding: utf-8 -*-

import uuid
import hashlib
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError
from ..utils import rabbitmq_sender

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = 'pos.order'

    order_id_custom = fields.Char(
        string='Order ID (UUID)',
        help='UUID voor RabbitMQ integratie',
        readonly=True,
        copy=False,
        index=True
    )

    payment_type = fields.Selection([
        ('Direct', 'Direct'),
        ('Invoice', 'Invoice')
    ], string='Payment Type', compute='_compute_payment_type', store=True, readonly=True)

    @api.depends('payment_ids', 'payment_ids.payment_method_id', 'to_invoice')
    def _compute_payment_type(self):
        """
        Bepaal payment type op basis van payment methods en factuurstatus:
        - Cash of Bancontact = Direct
        - Invoice = Invoice
        """
        for order in self:
            payment_type = 'Direct'  # Default

            if order.to_invoice:
                payment_type = 'Invoice'
            elif order.payment_ids:
                for payment in order.payment_ids:
                    if payment.payment_method_id:
                        payment_name = payment.payment_method_id.name.lower()
                        if 'invoice' in payment_name:
                            payment_type = 'Invoice'
                            break

            order.payment_type = payment_type

    @api.model_create_multi
    def create(self, vals_list):
        """Override create om UUID te genereren voor order_id_custom."""
        for vals in vals_list:
            if not vals.get('order_id_custom'):
                vals['order_id_custom'] = str(uuid.uuid4())

        return super(PosOrder, self).create(vals_list)

    def _build_payment_confirmed_data(self):
        """
        Bouw het data-dict voor Contract 16 (PaymentConfirmed → CRM).

        Verplichte velden: email, amount, currency, paidAt
        Optionele velden: userId
        """
        self.ensure_one()

        partner = self.partner_id

        return {
            'userId': partner.user_id_custom if partner else None,
            'email': partner.email if partner else '',
            'amount': self.amount_total,
            'currency': 'EUR',
            'paidAt': self.date_order.strftime('%Y-%m-%dT%H:%M:%SZ') if self.date_order else None,
        }

    def _build_invoice_requested_data(self):
        """
        Bouw het data-dict voor Contract K-01 (InvoiceRequested → Facturatie).
        Nu voor private individuals (US-11) inclusief volledige gebruikersdata.

        Verplichte velden: orderId, user (nested), amount, currency, orderedAt, items
        """
        self.ensure_one()

        partner = self.partner_id
        names = (partner.name or "").split(" ", 1)
        first_name = names[0]
        last_name = names[1] if len(names) > 1 else ""

        raw_role = partner.role or 'VISITOR'
        # Map 'Customer' naar een geldige waarde conform XSD schema
        if raw_role == 'Customer':
            role = 'COMPANY_CONTACT' if partner.company_id_custom else 'VISITOR'
        else:
            role = raw_role

        user_data = {
            'userId': partner.user_id_custom or '',
            'firstName': first_name,
            'lastName': last_name,
            'email': partner.email or '',
            'badgeCode': partner.badge_code or '',
            'role': role,
        }

        items = []
        for line in self.lines:
            items.append({
                'productName': line.product_id.name,
                'quantity': int(line.qty),
                'unitPrice': line.price_unit,
            })

        return {
            'orderId': self.order_id_custom,
            'user': user_data,
            'amount': self.amount_total,
            'currency': 'EUR',
            'orderedAt': self.date_order.strftime('%Y-%m-%dT%H:%M:%SZ') if self.date_order else None,
            'items': items,
        }

    def _get_tax_rate_for_product(self, product):
        """
        Map product category to VAT rate (6% for Food, 21% for Drinks/other).
        
        Args:
            product: product.product record
            
        Returns:
            float: Tax rate (6.0 or 21.0)
        """
        if not product or not product.categ_id:
            return 21.0
        
        category_name = (product.categ_id.name or "").lower().strip()
        
        # Food → 6% VAT
        if category_name == "food":
            return 6.0
        
        # Drinks → 21% VAT (alcoholic beverages)
        if category_name == "drinks":
            return 21.0
        
        # Default to 21%
        return 21.0

    def _build_gks_vat_breakdown(self):
        """
        Bouw een VAT-breakdown payload geschikt voor het GKS ticket.

        Retourneert een dict met netto en btw bedragen per tarief (6% en 21%),
        plus totalen. Deze helper probeert eerst de tax info van de orderlijn
        te gebruiken (`line.tax_ids`), en valt terug naar product category mapping.

        Resultaatvoorbeeld:
        {
            'rates': {
                6: {'net': 3.5, 'vat': 0.21},
                21: {'net': 3.98, 'vat': 0.83}
            },
            'net_total': 7.48,
            'vat_total': 1.04,
            'gross_total': 8.52
        }
        """
        self.ensure_one()

        rates = {6: {'net': 0.0, 'vat': 0.0}, 21: {'net': 0.0, 'vat': 0.0}}
        net_total = 0.0
        vat_total = 0.0
        gross_total = 0.0

        for line in self.lines:
            try:
                qty = float(line.qty)
            except Exception:
                qty = 0.0

            try:
                unit_price = float(line.price_unit)
            except Exception:
                unit_price = 0.0

            # Calculation: Qty × Unit Price = Gross (including VAT)
            gross = unit_price * qty
            gross_total += gross

            # Determine VAT rate: 
            # 1) Prefer line.tax_ids if available
            rate = None
            if hasattr(line, 'tax_ids') and line.tax_ids:
                try:
                    rate = float(line.tax_ids[0].amount)
                except Exception:
                    rate = None
            
            # 2) Fallback to product category mapping
            if rate is None and line.product_id:
                rate = self._get_tax_rate_for_product(line.product_id)
            
            # 3) Default to 21% if all else fails
            if rate is None:
                rate = 21.0

            # Calculate net from gross: net = gross / (1 + rate/100)
            net = gross / (1.0 + (rate / 100.0)) if rate >= 0 else gross
            vat = gross - net

            # Aggregate by rate group
            key = 6 if int(round(rate)) == 6 else 21
            rates[key]['net'] += round(net, 2)
            rates[key]['vat'] += round(vat, 2)
            net_total += net
            vat_total += vat

        return {
            'rates': rates,
            'net_total': round(net_total, 2),
            'vat_total': round(vat_total, 2),
            'gross_total': round(gross_total, 2)
        }

    def _build_vsc_code(self):
        """Build a 20-character VAT Signature Code from order data."""
        self.ensure_one()
        timestamp = self.date_order.strftime('%Y-%m-%dT%H:%M:%SZ') if self.date_order else ''
        source = f"{self.id}:{timestamp}:{self.amount_total}"
        # In production this value would be generated by the Fiscal Data Module
        # (Black Box) to keep the signature trusted and reduce tax fraud risk.
        digest = hashlib.sha256(source.encode('utf-8')).hexdigest().upper()
        return digest[:20]

    def export_for_printing(self):
        """Build a GKS receipt payload dict for this order.

        NOTE: In Odoo 17 the ``export_for_printing`` method no longer exists on
        the Python ``pos.order`` model — it was moved entirely to the JavaScript
        frontend.  Calling ``super().export_for_printing()`` therefore raises
        ``AttributeError: 'super' object has no attribute 'export_for_printing'``.

        We build the GKS-specific payload here from scratch and return it.
        The frontend receipt component fetches the VSC code independently via the
        ``/kassa_pos/get_vsc_code`` RPC endpoint, so nothing is lost.
        """
        _logger.info("🔵 export_for_printing CALLED for order_id=%s", self.id)

        # Build a standalone GKS data dict — no super() call because Odoo 17
        # does not expose export_for_printing on the Python model.
        data = {}

        if self:
            breakdown = self._build_gks_vat_breakdown()
            data['gks_vat_breakdown'] = breakdown
            data['vsc_code'] = self._build_vsc_code()
            data['gks_vsc'] = data['vsc_code']
            data['gks_order_id'] = self.id
            # Add id and server_id for frontend RPC lookups
            data['id'] = self.id
            data['server_id'] = self.id

            _logger.info("🟢 export_for_printing: ADDED id=%s server_id=%s vsc_code=%s", self.id, self.id, data['vsc_code'])
            _logger.info("🟣 export_for_printing: data dict has %d keys: %s", len(data.keys()), list(data.keys()))

            # Also expose per-group gross totals so the template can render totals
            # directly from the backend-calculated groups if needed.
            data['gks_vat_breakdown']['rates'][6]['gross'] = round(
                data['gks_vat_breakdown']['rates'][6]['net'] + data['gks_vat_breakdown']['rates'][6]['vat'], 2
            )
            data['gks_vat_breakdown']['rates'][21]['gross'] = round(
                data['gks_vat_breakdown']['rates'][21]['net'] + data['gks_vat_breakdown']['rates'][21]['vat'], 2
            )

        return data

    @api.model
    def create_from_ui(self, orders, draft=False):
        """
        Override van de POS frontend call.
        Na het verwerken van de order → stuur berichten naar RabbitMQ en verwerk saldo.
        """
        # Server-side guard: FIRST check Invoice payment restrictions BEFORE creating orders
        for order_data in orders:
            # Order data structure has payment info in order_data['data']
            order_dict = order_data.get('data', {})
            
            # Get payment lines from order data - stored in statement_ids
            payments = order_dict.get('statement_ids', [])
            _logger.info("🔍 create_from_ui: statement_ids=%s", payments)
            
            # Check if any payment is Invoice
            is_invoice = False
            for payment_line in payments:
                _logger.info("🔍 create_from_ui: payment_line=%s", payment_line)
                
                # payment_line format: (0, False, {dict_with_payment_data})
                if isinstance(payment_line, (list, tuple)) and len(payment_line) >= 3:
                    payment_data = payment_line[2]
                    payment_method_id = payment_data.get('payment_method_id')
                    _logger.info("🔍 create_from_ui: payment_method_id=%s from data=%s", payment_method_id, payment_data)
                    
                    if payment_method_id:
                        try:
                            payment_method = self.env['pos.payment.method'].browse(payment_method_id)
                            method_name = payment_method.name if payment_method else 'NOT_FOUND'
                            _logger.warning("🔍 create_from_ui: payment_method.name=%s", method_name)
                            
                            if payment_method and 'invoice' in (method_name or '').lower():
                                is_invoice = True
                                _logger.error("❌ create_from_ui: INVOICE METHOD DETECTED: %s", method_name)
                                break
                        except Exception as e:
                            _logger.warning("🔍 create_from_ui: exception browsing payment method: %s", e)
            
            _logger.info("🔍 create_from_ui: is_invoice=%s", is_invoice)
            
            # Check partner company_id_custom
            if is_invoice:
                partner_id = order_dict.get('partner_id')
                _logger.info("🔍 create_from_ui: partner_id=%s for invoice order", partner_id)
                
                if partner_id:
                    partner = self.env['res.partner'].browse(partner_id)
                    user_id = partner.user_id_custom if partner else False
                    has_company = partner.company_id_custom if partner else False
                    _logger.info("🟢 create_from_ui: INVOICE + partner_id=%s user_id_custom=%s company_id_custom=%s", 
                                 partner_id, user_id, has_company)
                    
                    if partner and not partner.company_id_custom:
                        _logger.info("ℹ️ create_from_ui: Invoice payment for partner WITHOUT company (Particulier/US-11 path)")
        
        # Now create orders
        order_ids = super().create_from_ui(orders, draft=draft)

        # Build a set of order references that were submitted with an Invoice
        # payment method.  We detect this from the raw input (before super()) so
        # we don't depend on the `payment_type` computed field being flushed yet.
        invoice_refs = set()
        for order_data in orders:
            od = order_data.get('data', {})
            for pl in od.get('statement_ids', []):
                if isinstance(pl, (list, tuple)) and len(pl) >= 3:
                    pm_id = pl[2].get('payment_method_id')
                    if pm_id:
                        try:
                            pm = self.env['pos.payment.method'].browse(pm_id)
                            if pm and 'invoice' in (pm.name or '').lower():
                                invoice_refs.add(od.get('pos_reference') or od.get('name'))
                        except Exception:
                            pass

        for order_info in order_ids:
            order = self.browse(order_info['id'])

            # Ensure the frontend receives the server-side print payload
            # including the generated `vsc_code`. Some POS flows print
            # immediately after create_from_ui and rely on the returned
            # payload instead of making an extra RPC; attach it here so
            # the receipt component can read `props.data.vsc_code`.
            try:
                exported = order.export_for_printing() or {}
                _logger.info("🟦 create_from_ui: export_for_printing returned %d keys: %s", len(exported.keys()), list(exported.keys()))

                order_info['data'] = exported
                _logger.info("🟪 create_from_ui: order_info['data'] now contains %d keys: %s", len(order_info.get('data', {}).keys()), list(order_info.get('data', {}).keys()))

                # Also expose the VSC directly at the top level for clients
                # that don't inspect `data`.
                if 'vsc_code' in exported:
                    order_info['vsc_code'] = exported.get('vsc_code')
                    _logger.info("🔷 create_from_ui: SET order_info['vsc_code']=%s and order_info['data']['vsc_code']=%s", order_info.get('vsc_code'), order_info.get('data', {}).get('vsc_code'))
                try:
                    _logger.info("✅ create_from_ui COMPLETE: order_id=%s vsc=%s exported_keys=%s", order.id, order_info.get('vsc_code'), list(exported.keys()))
                except Exception:
                    pass
            except Exception as e:
                _logger.error("❌ create_from_ui: export_for_printing FAILED for order_id=%s error=%s", order.id, str(e))

            # Determine whether this order used an Invoice payment method.
            # We check both the pre-detected set (reliable) and the stored
            # computed field (may already be flushed by now) as a fallback.
            is_invoice_order = (
                order.pos_reference in invoice_refs
                or order.payment_type == 'Invoice'
            )
            _logger.info(
                "🐇 create_from_ui: order_id=%s state=%s payment_type=%s pos_ref=%s is_invoice_order=%s",
                order.id, order.state, order.payment_type,
                order.pos_reference, is_invoice_order,
            )

            # Invoice-payment orders are in state 'draft' at this point because
            # Odoo generates the account.move asynchronously (account_move=False
            # in the sync result).  Always trigger for invoice orders; for direct
            # payments use the state guard as before.
            if order.state in ('paid', 'done', 'invoiced') or is_invoice_order:
                _logger.info("🐇 create_from_ui: calling _trigger_rabbitmq_messages for order_id=%s", order.id)
                self._trigger_rabbitmq_messages(order, is_invoice=is_invoice_order)
                self._process_balance_payment(order)
            else:
                _logger.info(
                    "🐇 create_from_ui: SKIPPING rabbitmq for order_id=%s (state=%s, not invoice)",
                    order.id, order.state,
                )

        return order_ids

    def _process_balance_payment(self, order):
        """Verwerk saldo-betalingen: deducteer van partner balance en sla transactie op."""
        if not order.partner_id:
            return
        partner = order.partner_id

        # Process payments sequentially; if a Top Up payment exceeds the available
        # balance, deduct only the available amount and create a new payment for
        # the remainder using a non-Top Up payment method from the POS config.
        for payment in order.payment_ids.sorted(key=lambda r: r.id):
            if not payment.payment_method_id:
                continue

            payment_name = (payment.payment_method_id.name or '').lower()
            if 'saldo' not in payment_name and 'top up' not in payment_name:
                continue

            available = float(partner.balance or 0.0)
            requested = float(payment.amount or 0.0)

            # Determine how much to deduct from balance
            if available <= 0.0:
                deduct = 0.0
                remaining = requested
            elif requested <= available:
                deduct = requested
                remaining = 0.0
            else:
                deduct = available
                remaining = requested - deduct

            # Apply deduction (if any)
            if deduct > 0.0:
                new_balance = round(available - deduct, 2)
                partner.write({'balance': new_balance})
                self.env['balance.transaction'].create({
                    'partner_id': partner.id,
                    'amount': -deduct,
                    'transaction_type': 'payment',
                    'payment_method': 'balance',
                    'note': f'Top Up betaling — order {order.name}',
                    'pos_order_id': order.id,
                    'balance_after': new_balance,
                })
                try:
                    payment.write({'amount': deduct})
                except Exception:
                    _logger.exception('Failed to adjust Top Up payment amount for order %s', order.name)

            # If there's a remainder, create a new payment using another payment method
            if remaining > 0.0:
                _logger.info('Top Up balance insufficient for order %s: deduct=%.2f remaining=%.2f', order.name, deduct, remaining)

                # Try to find an alternative payment method from the POS config
                alt_method = None
                try:
                    config = getattr(order.session_id, 'config_id', None) or getattr(order.session_id, 'config', None)
                    if config and getattr(config, 'payment_method_ids', False):
                        for m in config.payment_method_ids:
                            mname = (m.name or '').lower()
                            if 'saldo' in mname or 'top up' in mname:
                                continue
                            alt_method = m
                            break

                    if not alt_method:
                        # Fallback: first non-Top Up method in system
                        alt_method = self.env['pos.payment.method'].search([('name', 'not ilike', 'top up')], limit=1)
                except Exception:
                    _logger.exception('Error selecting alternative payment method for order %s', order.name)

                if not alt_method or not alt_method.id:
                    _logger.warning('No alternative payment method found for order %s; remaining amount %.2f will stay as unpaid', order.name, remaining)
                else:
                    try:
                        self.env['pos.payment'].create({
                            'order_id': order.id,
                            'amount': remaining,
                            'payment_method_id': alt_method.id,
                            'journal_id': getattr(alt_method, 'journal_id', False) and alt_method.journal_id.id or False,
                        })
                        _logger.info('Created fallback payment (%.2f) using %s for order %s', remaining, alt_method.name, order.name)
                    except Exception:
                        _logger.exception('Failed to create fallback payment for order %s', order.name)

    def _trigger_rabbitmq_messages(self, order, is_invoice=False):
        """
        Routing rules for RabbitMQ messages per order:

        ┌─────────────────────────┬────────────────────┬─────────────────────────────────┐
        │ Partner                 │ Payment method     │ Action                          │
        ├─────────────────────────┼────────────────────┼─────────────────────────────────┤
        │ has company_id_custom   │ Invoice            │ NOTHING — deferred to BatchClosed│
        │ no company_id_custom    │ Invoice            │ InvoiceRequested (K-01)         │
        │ any                     │ Direct (cash/…)    │ PaymentConfirmed (Contract 16)  │
        └─────────────────────────┴────────────────────┴─────────────────────────────────┘
        """
        partner = order.partner_id
        has_company = bool(partner.company_id_custom) if partner else False
        invoice_payment = is_invoice or order.payment_type == 'Invoice'

        _logger.info(
            "🐇 _trigger_rabbitmq_messages: order_id=%s state=%s invoice_payment=%s has_company=%s partner=%s",
            order.id, order.state, invoice_payment, has_company,
            partner.id if partner else None,
        )

        if invoice_payment and has_company:
            # B2B invoice: deferred to BatchClosed (Afsluitknop / K-02).
            # Do NOT send any per-order message to kassa.topic.
            _logger.info(
                "🐇 _trigger_rabbitmq_messages: DEFERRED (company invoice) order_id=%s — will appear in BatchClosed",
                order.id,
            )
            return

        if invoice_payment and not has_company:
            # Visitor/individual invoice (US-11): send InvoiceRequested immediately.
            if not partner:
                _logger.warning(
                    "🐇 _trigger_rabbitmq_messages: skipping InvoiceRequested — no partner for order_id=%s",
                    order.id,
                )
                return
            invoice_data = order._build_invoice_requested_data()
            _logger.info("🐇 _trigger_rabbitmq_messages: sending InvoiceRequested for order_id=%s", order.id)
            ok = rabbitmq_sender.send_invoice_requested(invoice_data)
            _logger.info("🐇 _trigger_rabbitmq_messages: send_invoice_requested result=%s", ok)
            return

        # Direct payment (cash / bancontact / saldo / …): send PaymentConfirmed.
        payment_data = order._build_payment_confirmed_data()
        if payment_data.get('email'):
            _logger.info("🐇 _trigger_rabbitmq_messages: sending PaymentConfirmed for order_id=%s", order.id)
            ok = rabbitmq_sender.send_payment_confirmed(payment_data)
            _logger.info("🐇 _trigger_rabbitmq_messages: send_payment_confirmed result=%s", ok)
        else:
            _logger.warning(
                "🐇 _trigger_rabbitmq_messages: skipping PaymentConfirmed — no email for order_id=%s",
                order.id,
            )

    @api.model
    def close_daily_batch(self, session=None, session_id=None) -> dict:
        """
        Afsluitknop: Collect today's transactions and send to facturatie.
        
        Args:
            session: Optional pos.session record
            session_id: Optional ID of the session (passed from JS UI)
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        try:
            # Resolve session
            if not session and session_id:
                session = self.env['pos.session'].browse(session_id)
            
            if not session:
                # Fallback: try to find the current active session for this user
                session = self.env['pos.session'].search([
                    ('state', 'in', ['opened', 'closing_control']),
                    ('user_id', '=', self.env.uid)
                ], limit=1)
            
            if not session or not session.exists():
                return {
                    'success': False,
                    'message': 'Geen actieve POS sessie gevonden voor deze gebruiker. Controleer of de kassa open staat.',
                    'batch_id': None,
                    'orders_count': 0,
                    'total_amount': 0.0
                }
            
            # Use the batch service to close
            from ..services import PosOrderBatchService
            service = PosOrderBatchService(self.env)
            
            # Close the session
            success, error_msg, batch_data = service.close_session(session)
            
            if not success:
                return {
                    'success': False,
                    'message': f'Error closing batch: {error_msg}',
                    'batch_id': None,
                    'orders_count': 0,
                    'total_amount': 0.0
                }
            
            if not batch_data:
                # No qualifying orders
                return {
                    'success': True,
                    'message': 'No orders to process (all direct payments or unidentified customers)',
                    'batch_id': None,
                    'orders_count': 0,
                    'total_amount': 0.0
                }
            
            # Get the batch record for this batch
            batch_record = self.env['pos.order.batch'].get_batch_for_uuid(batch_data['batchId'])
            
            # Publish to RabbitMQ
            success, error_msg = service.publish_batch(batch_data, batch_record)
            
            if not success:
                return {
                    'success': False,
                    'message': f'Error publishing batch: {error_msg}',
                    'batch_id': batch_data['batchId'],
                    'orders_count': batch_data['totalOrders'],
                    'total_amount': batch_data['totalAmount']
                }
            
            _logger.info(f"Successfully closed batch {batch_record.name}")
            
            return {
                'success': True,
                'message': 'Batch closed and sent to facturatie system',
                'batch_id': batch_data['batchId'],
                'orders_count': batch_data['totalOrders'],
                'total_amount': batch_data['totalAmount']
            }
        
        except Exception as e:
            _logger.exception(f"Error in close_daily_batch: {str(e)}")
            return {
                'success': False,
                'message': f'Unexpected error: {str(e)}',
                'batch_id': None,
                'orders_count': 0,
                'total_amount': 0.0
            }

