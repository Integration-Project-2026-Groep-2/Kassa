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

    # ── 0. Ensure Chart of Accounts is configured ────────────────────────────
    try:
        Company = env.ref('base.main_company')
        has_coa = env['account.account'].sudo().search([('company_id', '=', Company.id)], limit=1)
        if not has_coa:
            import logging
            logging.getLogger('kassa_pos').info("post_init: No chart of accounts found. Loading generic_coa...")
            env['account.chart.template'].sudo().try_loading('generic_coa', company=Company)
            logging.getLogger('kassa_pos').info("post_init: generic_coa loaded successfully.")
    except Exception:
        try:
            import logging
            logging.getLogger('kassa_pos').exception('post_init: failed to load chart of accounts')
        except Exception:
            pass

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
            existing_xml = IrModelData.search([('module', '=', 'kassa_pos'), ('name', '=', xml_name)], limit=1)
            if existing_xml:
                if env['account.journal'].browse(existing_xml.res_id).exists():
                    continue
                else:
                    existing_xml.unlink()

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
            existing_xml = IrModelData.search([('module', '=', 'kassa_pos'), ('name', '=', 'pos_config_kassa_main')], limit=1)
            if not existing_xml:
                IrModelData.create({
                    'module': 'kassa_pos',
                    'name': 'pos_config_kassa_main',
                    'model': 'pos.config',
                    'res_id': existing.id,
                    'noupdate': True,
                })
            else:
                if existing_xml.res_id != existing.id:
                    existing_xml.write({'res_id': existing.id})
    except Exception:
        try:
            import logging
            logging.getLogger('kassa_pos').exception('post_init: failed to create pos.config')
        except Exception:
            pass
    # ── 3b. Cleanup: remove any foreign/generic 'Cash' PM from Kassa Main ────
    # On the first run the code may have linked Odoo's default 'Cash' payment
    # method (owned by the built-in 'Shop' POS) to Kassa Main. Odoo's own
    # constraint then blocks re-opening Kassa Main with that shared cash PM.
    # We remove that stale link here so Step 4 can replace it with our own
    # dedicated 'Kassa Cash' payment method.
    try:
        cr.execute("""
            SELECT res_id FROM ir_model_data
            WHERE module='kassa_pos' AND name='pos_config_kassa_main'
        """)
        row = cr.fetchone()
        if row:
            pos_config_id = row[0]
            # Find payment methods linked to Kassa Main whose xml_name is NOT
            # in our expected set (i.e. they are foreign/default records).
            our_pm_xml_names = (
                'payment_method_cash', 'payment_method_card',
                'payment_method_invoice', 'pos_payment_method_topup',
            )
            cr.execute("""
                SELECT res_id FROM ir_model_data
                WHERE module='kassa_pos' AND name = ANY(%s)
            """, (list(our_pm_xml_names),))
            our_pm_ids = [r[0] for r in cr.fetchall()]

            # Remove any linked PM that is NOT in our managed set
            if our_pm_ids:
                cr.execute("""
                    DELETE FROM pos_config_pos_payment_method_rel
                    WHERE pos_config_id = %s
                      AND pos_payment_method_id NOT IN %s
                """, (pos_config_id, tuple(our_pm_ids)))
            else:
                cr.execute("""
                    DELETE FROM pos_config_pos_payment_method_rel
                    WHERE pos_config_id = %s
                """, (pos_config_id,))
    except Exception:
        try:
            import logging
            logging.getLogger('kassa_pos').exception('post_init: cleanup of foreign cash PM failed')
        except Exception:
            pass

    # ── 4. Create POS payment methods safely ─────────────────────────────────
    try:
        PaymentMethod = env['pos.payment.method'].sudo()
        IrModelData = env['ir.model.data'].sudo()
        Company = env.ref('base.main_company')
        
        # Define payment methods
        # NOTE: Use distinct names (e.g. 'Kassa Cash') so we never accidentally
        # match Odoo's built-in 'Cash' payment method, which is already
        # exclusively owned by the default 'Shop' POS configuration.
        payment_methods = [
            ('payment_method_cash', 'Kassa Cash', 'account_journal_cash_kassa'),
            ('payment_method_card', 'Bancontact', 'account_journal_bancontact_kassa'),
            ('payment_method_invoice', 'Invoice', 'account_journal_bancontact_kassa'),
            ('pos_payment_method_topup', 'Saldo', 'account_journal_saldo_kassa'),
        ]
        
        for xml_name, display_name, journal_xmlid in payment_methods:
            # Try to resolve the existing record ID
            pm_id = None
            existing_xml = IrModelData.search([('module', '=', 'kassa_pos'), ('name', '=', xml_name)], limit=1)
            if existing_xml:
                if env['pos.payment.method'].browse(existing_xml.res_id).exists():
                    pm_id = existing_xml.res_id
                else:
                    existing_xml.unlink()

            if not pm_id:
                existing = PaymentMethod.search([('name', '=', display_name)], limit=1)
                if existing:
                    # Guard: a cash-type payment method may only belong to one POS.
                    # If this record is already linked exclusively to a different POS
                    # config (not Kassa Main), don't reuse it — let the else-branch
                    # create a fresh dedicated one.
                    kassa_main = env['pos.config'].sudo().search([('name', '=', 'Kassa Main')], limit=1)
                    is_cash_type = existing.journal_id and existing.journal_id.type == 'cash'
                    already_owned_by_other = False
                    if is_cash_type and 'pos_config_ids' in existing._fields:
                        other_pos = existing.pos_config_ids.filtered(
                            lambda c: not kassa_main or c.id != kassa_main.id
                        )
                        already_owned_by_other = bool(other_pos)

                    if not already_owned_by_other:
                        pm_id = existing.id
                        # Register in ir.model.data
                        IrModelData.create({
                            'module': 'kassa_pos',
                            'name': xml_name,
                            'model': 'pos.payment.method',
                            'res_id': pm_id,
                            'noupdate': True,
                        })

            # Resolve journal ref
            journal = None
            try:
                journal = env.ref('kassa_pos.' + journal_xmlid, raise_if_not_found=False)
            except Exception:
                journal = None

            # Prepare values to set or update
            vals = {}
            if journal:
                vals['journal_id'] = journal.id
            if xml_name == 'payment_method_invoice':
                if 'split_transactions' in PaymentMethod._fields:
                    vals['split_transactions'] = True
                if 'identify_customer' in PaymentMethod._fields:
                    vals['identify_customer'] = True
            elif xml_name == 'pos_payment_method_topup':
                if 'identify_customer' in PaymentMethod._fields:
                    vals['identify_customer'] = True

            if pm_id:
                # Update existing record if any values differ
                pm = PaymentMethod.browse(pm_id)
                update_vals = {k: v for k, v in vals.items() if getattr(pm, k) != v}
                if update_vals:
                    pm.write(update_vals)
            else:
                # Create a new payment method
                create_vals = {
                    'name': display_name,
                    'company_id': Company.id,
                }
                create_vals.update(vals)
                pm = PaymentMethod.create(create_vals)
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
