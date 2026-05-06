# -*- coding: utf-8 -*-

from odoo import SUPERUSER_ID, api

from . import utils
from . import models
from . import controllers


def pre_init_hook(cr):
    """Ensure the POS journals exist before XML payment methods are loaded."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    journal_model = env['account.journal'].with_context(mail_create_nolog=True)
    ir_model_data = env['ir.model.data']

    journal_specs = [
        ('kassa_pos.account_journal_cash_kassa', 'Kassa Cash', 'KCASH', 'cash'),
        ('kassa_pos.account_journal_bancontact_kassa', 'Kassa Bancontact', 'KBANC', 'bank'),
        ('kassa_pos.account_journal_saldo_kassa', 'Kassa Saldo', 'KSALDO', 'bank'),
    ]

    company = env.company
    for xml_id, name, code, journal_type in journal_specs:
        journal = env.ref(xml_id, raise_if_not_found=False)
        if not journal:
            journal = journal_model.search([
                ('code', '=', code),
                ('company_id', '=', company.id),
            ], limit=1)
        if not journal:
            journal = journal_model.create({
                'name': name,
                'code': code,
                'type': journal_type,
                'company_id': company.id,
            })
        ir_model_data._update_xmlids([{
            'xml_id': xml_id,
            'record': journal,
            'noupdate': True,
        }])


def post_init(cr, registry):
    """Post-init hook: ensure res_partner.balance column exists."""
    # Check if column exists
    cr.execute("""
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='res_partner' AND column_name='balance'
    """)
    
    if not cr.fetchone():
        # Column doesn't exist, create it
        cr.execute("""
            ALTER TABLE res_partner 
            ADD COLUMN balance numeric(10,2) DEFAULT 0.0
        """)


