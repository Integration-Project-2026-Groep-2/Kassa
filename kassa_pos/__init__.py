# -*- coding: utf-8 -*-

from odoo import SUPERUSER_ID, api

from . import utils
from . import models
from . import controllers


def post_init(env):
    """Post-init hook: runs after fresh install.

    Responsibilities:
    1. Ensure the res.partner.balance column exists (schema migration).
    2. Create pos.config and payment methods safely to avoid ORM write restrictions.
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

    # ── 2. Create pos.config safely ──────────────────────────────────────────
    try:
        PosConfig = env['pos.config'].sudo()
        IrModelData = env['ir.model.data'].sudo()
        Company = env.ref('base.main_company')
        
        # Check if pos_config_kassa_main already exists
        existing = PosConfig.search([('name', '=', 'Kassa Main')], limit=1)
        if not existing:
            # Create pos.config record
            pos_config = PosConfig.create({
                'name': 'Kassa Main',
                'company_id': Company.id,
                'module_pos_restaurant': False,
                'cash_control': True,
            })
            # Register in ir.model.data
            IrModelData.create({
                'module': 'kassa_pos',
                'name': 'pos_config_kassa_main',
                'model': 'pos.config',
                'res_id': pos_config.id,
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
                })
    except Exception:
        try:
            import logging
            logging.getLogger('kassa_pos').exception('post_init: failed to create pos.config')
        except Exception:
            pass
    # ── 3. Create POS payment methods safely ─────────────────────────────────
    try:
        PaymentMethod = env['pos.payment.method'].sudo()
        IrModelData = env['ir.model.data'].sudo()
        Company = env.ref('base.main_company')
        
        # Define payment methods
        payment_methods = [
            ('payment_method_cash', 'Cash', 'account_journal_cash_kassa'),
            ('payment_method_card', 'Bancontact', 'account_journal_bancontact_kassa'),
            ('payment_method_invoice', 'Invoice', 'account_journal_bancontact_kassa'),
            ('pos_payment_method_topup', 'Top Up', 'account_journal_saldo_kassa'),
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
            if xml_name == 'payment_method_invoice':
                vals['split_transactions'] = True
            
            pm = PaymentMethod.create(vals)
            IrModelData.create({
                'module': 'kassa_pos',
                'name': xml_name,
                'model': 'pos.payment.method',
                'res_id': pm.id,
            })
    except Exception:
        try:
            import logging
            logging.getLogger('kassa_pos').exception('post_init: failed to create payment methods')
        except Exception:
            pass

    # ── 4. Link payment methods to pos.config ────────────────────────────────
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
