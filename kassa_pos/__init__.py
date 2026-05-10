# -*- coding: utf-8 -*-

from odoo import SUPERUSER_ID, api

from . import utils
from . import models
from . import controllers


def post_init(env):
    """Post-init hook: runs after fresh install.

    Responsibilities:
    1. Ensure the res.partner.balance column exists (schema migration).
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
    # ── 2. Ensure POS payment methods exist (safe ORM create) ──────────────
    try:
        PaymentMethod = env['pos.payment.method'].sudo()
        IrModelData = env['ir.model.data'].sudo()
        Company = env.ref('base.main_company')

        pm_defs = [
            ('payment_method_cash', 'Cash', 'kassa_pos.account_journal_cash_kassa', {}),
            ('payment_method_card', 'Bancontact', 'kassa_pos.account_journal_bancontact_kassa', {}),
            ('payment_method_invoice', 'Invoice', 'kassa_pos.account_journal_bancontact_kassa', {'split_transactions': True}),
            ('pos_payment_method_topup', 'Top Up', 'kassa_pos.account_journal_saldo_kassa', {}),
        ]

        for xml_name, display_name, journal_xmlid, extra in pm_defs:
            # skip if xmlid already mapped
            try:
                IrModelData.get_object('kassa_pos', xml_name)
                continue
            except Exception:
                pass

            # try to find by name first
            existing = PaymentMethod.search([('name', 'ilike', display_name)], limit=1)
            if existing:
                # register ir.model.data if missing
                IrModelData.create({'module': 'kassa_pos', 'name': xml_name, 'model': 'pos.payment.method', 'res_id': existing.id})
                continue

            # resolve journal
            journal = None
            try:
                journal = env.ref(journal_xmlid, raise_if_not_found=False)
            except Exception:
                journal = None

            vals = {'name': display_name, 'company_id': Company.id}
            if journal:
                vals['journal_id'] = journal.id
            vals.update(extra)

            pm = PaymentMethod.create(vals)
            IrModelData.create({'module': 'kassa_pos', 'name': xml_name, 'model': 'pos.payment.method', 'res_id': pm.id})
    except Exception:
        try:
            import logging
            logging.getLogger('kassa_pos').exception('post_init: failed to ensure pos payment methods')
        except Exception:
            pass
    # ── 2. Ensure POS payment method links exist ────────────────────────────
    # Insert into pos_config_pos_payment_method_rel directly via SQL to avoid
    # triggering ORM 'write' checks about open sessions during module install.
    try:
        # Get pos_config id (from xmlid) and payment method ids
        cr.execute("SELECT res_id FROM ir_model_data WHERE module='kassa_pos' AND name='pos_config_kassa_main'")
        row = cr.fetchone()
        if row:
            pos_config_id = row[0]
            # payment method xml names
            pm_names = ['payment_method_cash', 'payment_method_card', 'payment_method_invoice', 'pos_payment_method_topup']
            for pm in pm_names:
                cr.execute("SELECT res_id FROM ir_model_data WHERE module='kassa_pos' AND name=%s", (pm,))
                pm_row = cr.fetchone()
                if pm_row:
                    pm_id = pm_row[0]
                    # insert relation if missing
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
        # don't fail installation for edge cases; log to server logs instead
        try:
            import logging
            logging.getLogger('kassa_pos').exception('post_init: failed to ensure pos payment links')
        except Exception:
            pass
