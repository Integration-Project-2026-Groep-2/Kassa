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

    # ── 00. Ensure EUR currency is active ────────────────────────────────────
    try:
        eur = env.ref('base.EUR', raise_if_not_found=False)
        if eur and not eur.active:
            import logging
            logging.getLogger('kassa_pos').info("post_init: Activating EUR currency defensively...")
            eur.sudo().write({'active': True})
    except Exception:
        try:
            import logging
            logging.getLogger('kassa_pos').exception('post_init: failed to activate EUR currency')
        except Exception:
            pass

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
    # ── 3b. Cleanup: remove any PM that is shared with another POS ────────────
    # Odoo enforces that a cash-type payment method may only belong to ONE POS.
    # If a PM is linked to both Kassa Main AND another POS config, Odoo's
    # constraint blocks opening Kassa Main. We fix this by:
    #   1. Removing the shared PM from Kassa Main's relation table.
    #   2. Deleting the ir.model.data entry for that PM so Step 4 will create
    #      a fresh dedicated PM (e.g. 'Kassa Cash') in its place.
    try:
        import logging as _logging
        _log_cleanup = _logging.getLogger('kassa_pos')

        cr.execute("""
            SELECT res_id FROM ir_model_data
            WHERE module='kassa_pos' AND name='pos_config_kassa_main'
        """)
        row = cr.fetchone()
        if row:
            pos_config_id = row[0]

            # Fetch every PM currently linked to Kassa Main
            cr.execute("""
                SELECT pos_payment_method_id
                FROM pos_config_pos_payment_method_rel
                WHERE pos_config_id = %s
            """, (pos_config_id,))
            linked_pm_ids = [r[0] for r in cr.fetchall()]

            for pm_id in linked_pm_ids:
                # Check if this PM is ALSO linked to a different POS config
                cr.execute("""
                    SELECT pos_config_id
                    FROM pos_config_pos_payment_method_rel
                    WHERE pos_payment_method_id = %s
                      AND pos_config_id != %s
                    LIMIT 1
                """, (pm_id, pos_config_id))
                other_pos = cr.fetchone()
                if other_pos:
                    _log_cleanup.warning(
                        'post_init: PM id=%s is shared with POS id=%s — '
                        'removing from Kassa Main and resetting ir.model.data '
                        'so a dedicated copy is created.',
                        pm_id, other_pos[0],
                    )
                    # Remove from Kassa Main relation
                    cr.execute("""
                        DELETE FROM pos_config_pos_payment_method_rel
                        WHERE pos_config_id = %s AND pos_payment_method_id = %s
                    """, (pos_config_id, pm_id))
                    # Remove the ir.model.data entry so Step 4 recreates it fresh
                    cr.execute("""
                        DELETE FROM ir_model_data
                        WHERE module = 'kassa_pos'
                          AND model  = 'pos.payment.method'
                          AND res_id = %s
                    """, (pm_id,))
    except Exception:
        try:
            import logging
            logging.getLogger('kassa_pos').exception('post_init: cleanup of shared cash PM failed')
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

        # ── Pre-pass: deduplicate cash PMs sharing the same journal ──────────
        # Previous failed runs may have left multiple pos.payment.method records
        # all pointing at the same cash journal (KCASH). Odoo forbids this with
        # the constraint "cannot use same journal on multiple cash PMs".
        # We keep the record registered in our ir.model.data if possible,
        # otherwise keep the one with the lowest ID, and hard-delete the rest.
        for _xml_name, _display_name, _journal_xmlid in payment_methods:
            try:
                _journal = env.ref('kassa_pos.' + _journal_xmlid, raise_if_not_found=False)
                if not _journal or _journal.type != 'cash':
                    continue
                pms_on_journal = PaymentMethod.search([('journal_id', '=', _journal.id)])
                if len(pms_on_journal) <= 1:
                    continue
                # Prefer the one already in our ir.model.data
                our_xml = IrModelData.search([
                    ('module', '=', 'kassa_pos'),
                    ('name', '=', _xml_name),
                    ('model', '=', 'pos.payment.method'),
                ], limit=1)
                keep_id = our_xml.res_id if (our_xml and our_xml.res_id in pms_on_journal.ids) else pms_on_journal[0].id
                for _pm in pms_on_journal:
                    if _pm.id == keep_id:
                        continue
                    import logging as _l
                    _l.getLogger('kassa_pos').warning(
                        'post_init: dedup — deleting duplicate cash PM id=%s (journal=%s), keeping id=%s',
                        _pm.id, _journal.name, keep_id,
                    )
                    cr.execute(
                        'DELETE FROM pos_config_pos_payment_method_rel WHERE pos_payment_method_id = %s',
                        (_pm.id,),
                    )
                    cr.execute(
                        "DELETE FROM ir_model_data WHERE model='pos.payment.method' AND res_id = %s",
                        (_pm.id,),
                    )
                    _pm.unlink()
            except Exception:
                try:
                    import logging
                    logging.getLogger('kassa_pos').exception('post_init: cash PM dedup failed for %s', _xml_name)
                except Exception:
                    pass


        for xml_name, display_name, journal_xmlid in payment_methods:
            # ── Resolve the journal we intend to use ────────────────────────
            journal = None
            try:
                journal = env.ref('kassa_pos.' + journal_xmlid, raise_if_not_found=False)
            except Exception:
                journal = None

            # ── Try to resolve an existing PM record (3-stage lookup) ───────
            pm_id = None

            # Stage 1: XML ID in ir.model.data
            existing_xml = IrModelData.search([('module', '=', 'kassa_pos'), ('name', '=', xml_name)], limit=1)
            if existing_xml:
                if env['pos.payment.method'].browse(existing_xml.res_id).exists():
                    pm_id = existing_xml.res_id
                else:
                    existing_xml.unlink()

            # Stage 2: search by display name
            if not pm_id:
                existing = PaymentMethod.search([('name', '=', display_name)], limit=1)
                if existing:
                    # Guard: a cash PM may only belong to one POS.
                    # Skip if already exclusively owned by a different POS.
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
                        IrModelData.create({
                            'module': 'kassa_pos',
                            'name': xml_name,
                            'model': 'pos.payment.method',
                            'res_id': pm_id,
                            'noupdate': True,
                        })

            # Stage 3: search by journal — catches renamed/leftover PMs that
            # still use our journal (e.g. old 'Cash' → KCASH after cleanup).
            # Prevents the "same journal on multiple cash PMs" constraint error.
            if not pm_id and journal:
                by_journal = PaymentMethod.search([('journal_id', '=', journal.id)], limit=1)
                if by_journal:
                    pm_id = by_journal.id
                    # Rename it to our canonical name if it differs
                    if by_journal.name != display_name:
                        try:
                            by_journal.write({'name': display_name})
                        except Exception:
                            pass
                    IrModelData.create({
                        'module': 'kassa_pos',
                        'name': xml_name,
                        'model': 'pos.payment.method',
                        'res_id': pm_id,
                        'noupdate': True,
                    })


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
                # Update existing record if any values differ.
                # Many2one fields return a recordset, so compare by .id to
                # avoid the "unsupported operand for ==" UserWarning.
                pm = PaymentMethod.browse(pm_id)
                update_vals = {}
                for k, v in vals.items():
                    current = getattr(pm, k)
                    current_val = current.id if hasattr(current, 'id') else current
                    if current_val != v:
                        update_vals[k] = v
                if update_vals:
                    try:
                        pm.write(update_vals)
                    except Exception as write_err:
                        import logging
                        _log = logging.getLogger('kassa_pos')
                        _log.warning(
                            'post_init: skipping update of payment method %r — %s '
                            '(likely an open POS session is blocking the write; '
                            'close the session and restart to apply the update).',
                            display_name, write_err,
                        )
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
