# -*- coding: utf-8 -*-

# Append (not insert) so /app/src/odoo/ doesn't shadow the real Odoo package.
import sys
if '/app/src' not in sys.path:
    sys.path.append('/app/src')
try:
    from logging_config import configure_logging
    configure_logging()
except ImportError as e:
    print(f"kassa_pos: log handler not installed ({e})", file=sys.stderr)

from odoo import SUPERUSER_ID, api

from . import utils
from . import models
from . import controllers


def post_init(env):
    """Post-init hook: runs after fresh install.

    Responsibilities:
    1. Ensure the res.partner.balance column exists (schema migration).
    2. Create journals, pos.config and payment methods safely to avoid ORM write restrictions.
    """
    cr = env.cr

    # ── 1. Schema migration ──────────────────────────────────────────────────
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name='res_partner' AND column_name='balance'
    """)
    if not cr.fetchone():
        cr.execute("""
            ALTER TABLE res_partner
            ADD COLUMN balance numeric(10,2) DEFAULT 0.0
        """)

    # ── 2. Create account journals safely ────────────────────────────────────
    try:
        Journal = env['account.journal'].sudo()
        IrModelData = env['ir.model.data'].sudo()
        Company = env.ref('base.main_company')

        journals = [
            ('account_journal_cash_kassa', 'Kassa Cash', 'KCASH', 'cash'),
            ('account_journal_bancontact_kassa', 'Kassa Bancontact', 'KBANC', 'bank'),
            ('account_journal_saldo_kassa', 'Kassa Saldo', 'KSAL', 'bank'),
        ]

        for xml_name, display_name, code, journal_type in journals:
            try:
                IrModelData.get_object('kassa_pos', xml_name)
                continue
            except Exception:
                pass

            existing = Journal.search([('code', '=', code)], limit=1)
            if existing:
                try:
                    IrModelData.create({
                        'module': 'kassa_pos',
                        'name': xml_name,
                        'model': 'account.journal',
                        'res_id': existing.id,
                        'noupdate': True,
                    })
                except Exception:
                    pass
                continue

            journal = Journal.create({
                'name': display_name,
                'code': code,
                'type': journal_type,
                'company_id': Company.id,
            })
            IrModelData.create({
                'module': 'kassa_pos',
                'name': xml_name,
                'model': 'account.journal',
                'res_id': journal.id,
                'noupdate': True,
            })
    except Exception:
        try:
            import logging
            logging.getLogger('kassa_pos').exception('post_init: failed to create account journals')
        except Exception:
            pass

    # ── 3. Create pos.config safely ──────────────────────────────────────────
    try:
        PosConfig = env['pos.config'].sudo()
        IrModelData = env['ir.model.data'].sudo()
        Company = env.ref('base.main_company')
        
        # Check if pos_config_kassa_main already exists
        existing = PosConfig.search([('name', '=', 'Kassa Main')], limit=1)
        if not existing:
            # Create pos.config record
            vals = {
                'name': 'Kassa Main',
                'company_id': Company.id,
                'module_pos_restaurant': False,
            }
            if 'cash_control' in PosConfig._fields:
                vals['cash_control'] = True
            if 'journal_id' in PosConfig._fields:
                # Odoo 17 requires a Sales journal for pos.config.
                sales_journal = env['account.journal'].sudo().search([
                    ('type', '=', 'sale'),
                    ('company_id', '=', Company.id)
                ], limit=1)
                if sales_journal:
                    vals['journal_id'] = sales_journal.id
            pos_config = PosConfig.create(vals)
            # Register in ir.model.data
            IrModelData.create({
                'module': 'kassa_pos',
                'name': 'pos_config_kassa_main',
                'model': 'pos.config',
                'res_id': pos_config.id,
                'noupdate': True,
            })
        else:
            # Register existing in ir.model.data if missing
            try:
                IrModelData.get_object('kassa_pos', 'pos_config_kassa_main')
            except Exception:
                IrModelData.create({
                    'module': 'kassa_pos',
                    'name': 'pos_config_kassa_main',
                    'model': 'pos.config',
                    'res_id': existing.id,
                    'noupdate': True,
                })
    except Exception:
        try:
            import logging
            logging.getLogger('kassa_pos').exception('post_init: failed to create pos.config')
        except Exception:
            pass
    # ── 4. Create POS payment methods safely ─────────────────────────────────
    try:
        PaymentMethod = env['pos.payment.method'].sudo()
        IrModelData = env['ir.model.data'].sudo()
        Company = env.ref('base.main_company')
        
        # Define payment methods
        payment_methods = [
            ('payment_method_cash', 'Cash', 'account_journal_cash_kassa'),
            ('payment_method_card', 'Bancontact', 'account_journal_bancontact_kassa'),
            ('payment_method_invoice', 'Invoice', 'account_journal_bancontact_kassa'),
            ('pos_payment_method_topup', 'Saldo', 'account_journal_saldo_kassa'),
        ]
        
        for xml_name, display_name, journal_xmlid in payment_methods:
            # Check if already exists by xmlid mapping
            try:
                IrModelData.get_object('kassa_pos', xml_name)
                continue
            except Exception:
                pass
            
            # Try to find by name
            existing = PaymentMethod.search([('name', '=', display_name)], limit=1)
            if existing:
                # Register in ir.model.data
                IrModelData.create({
                    'module': 'kassa_pos',
                    'name': xml_name,
                    'model': 'pos.payment.method',
                    'res_id': existing.id,
                    'noupdate': True,
                })
                continue
            
            # Resolve journal ref
            journal = None
            try:
                journal = env.ref('kassa_pos.' + journal_xmlid, raise_if_not_found=False)
            except Exception:
                journal = None
            
            # Create payment method
            vals = {
                'name': display_name,
                'company_id': Company.id,
            }
            if journal:
                vals['journal_id'] = journal.id
            
            # Special handling for Invoice
            if xml_name == 'payment_method_invoice' and 'split_transactions' in PaymentMethod._fields:
                vals['split_transactions'] = True
            
            pm = PaymentMethod.create(vals)
            IrModelData.create({
                'module': 'kassa_pos',
                'name': xml_name,
                'model': 'pos.payment.method',
                'res_id': pm.id,
                'noupdate': True,
            })
    except Exception:
        try:
            import logging
            logging.getLogger('kassa_pos').exception('post_init: failed to create payment methods')
        except Exception:
            pass

    # ── 5. Link payment methods to pos.config ────────────────────────────────
    try:
        cr.execute("SELECT res_id FROM ir_model_data WHERE module='kassa_pos' AND name='pos_config_kassa_main'")
        row = cr.fetchone()
        if row:
            pos_config_id = row[0]
            pm_names = ['payment_method_cash', 'payment_method_card', 'payment_method_invoice', 'pos_payment_method_topup']
            for pm in pm_names:
                cr.execute("SELECT res_id FROM ir_model_data WHERE module='kassa_pos' AND name=%s", (pm,))
                pm_row = cr.fetchone()
                if pm_row:
                    pm_id = pm_row[0]
                    cr.execute(
                        "SELECT 1 FROM pos_config_pos_payment_method_rel WHERE pos_config_id=%s AND pos_payment_method_id=%s",
                        (pos_config_id, pm_id)
                    )
                    if not cr.fetchone():
                        cr.execute(
                            "INSERT INTO pos_config_pos_payment_method_rel (pos_config_id, pos_payment_method_id) VALUES (%s, %s)",
                            (pos_config_id, pm_id)
                        )
    except Exception:
        try:
            import logging
            logging.getLogger('kassa_pos').exception('post_init: failed to link payment methods')
        except Exception:
            pass
