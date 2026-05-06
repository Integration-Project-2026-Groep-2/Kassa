# -*- coding: utf-8 -*-

import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

MIN_TOPUP_AMOUNT = 5.0


class BalanceController(http.Controller):

    @http.route('/kassa/balance/search', type='json', auth='user', methods=['POST'])
    def search_partner(self, query=''):
        if not query or len(query.strip()) < 1:
            return []
        q = query.strip()
        partners = request.env['res.partner'].search([
            ('user_id_custom', '!=', False),
            '|', '|',
            ('name', 'ilike', q),
            ('email', 'ilike', q),
            ('badge_code', 'ilike', q),
        ], limit=10)
        return [{
            'id': p.id,
            'name': p.name or '',
            'email': p.email or '',
            'badge_code': p.badge_code or '',
            'balance': p.balance,
        } for p in partners]

    @http.route('/kassa/balance/topup', type='json', auth='user', methods=['POST'])
    def topup_balance(self, partner_id=None, amount=0.0, payment_method='cash'):
        if not partner_id:
            return {'success': False, 'error': 'Geen klant geselecteerd'}

        if amount < MIN_TOPUP_AMOUNT:
            return {'success': False, 'error': f'Minimum bedrag is €{MIN_TOPUP_AMOUNT:.2f}'}

        if payment_method not in ('cash', 'card'):
            return {'success': False, 'error': 'Ongeldige betaalmethode'}

        partner = request.env['res.partner'].browse(int(partner_id))
        if not partner.exists():
            return {'success': False, 'error': 'Klant niet gevonden'}

        new_balance = partner.balance + amount
        partner.write({'balance': new_balance})

        request.env['balance.transaction'].create({
            'partner_id': partner.id,
            'amount': amount,
            'transaction_type': 'topup',
            'payment_method': payment_method,
            'note': f'Saldo opladen via POS ({payment_method})',
            'balance_after': new_balance,
        })

        _logger.info('Saldo opgeladen: partner=%s bedrag=%.2f methode=%s nieuw_saldo=%.2f',
                     partner.name, amount, payment_method, new_balance)

        return {'success': True, 'new_balance': new_balance, 'name': partner.name}

    @http.route('/kassa/balance/deduct', type='json', auth='user', methods=['POST'])
    def deduct_balance(self, partner_id=None, amount=0.0, pos_order_id=None):
        if not partner_id:
            return {'success': False, 'error': 'Geen klant geselecteerd'}

        partner = request.env['res.partner'].browse(int(partner_id))
        if not partner.exists():
            return {'success': False, 'error': 'Klant niet gevonden'}

        if partner.balance < amount:
            return {'success': False, 'error': f'Onvoldoende saldo (€{partner.balance:.2f})'}

        new_balance = partner.balance - amount
        partner.write({'balance': new_balance})

        request.env['balance.transaction'].create({
            'partner_id': partner.id,
            'amount': -amount,
            'transaction_type': 'payment',
            'payment_method': 'balance',
            'note': 'Betaling via saldo',
            'pos_order_id': pos_order_id,
            'balance_after': new_balance,
        })

        return {'success': True, 'new_balance': new_balance}

    @http.route('/kassa/balance/get', type='json', auth='user', methods=['POST'])
    def get_balance(self, partner_id=None):
        if not partner_id:
            return {'success': False, 'error': 'Geen klant geselecteerd'}
        partner = request.env['res.partner'].browse(int(partner_id))
        if not partner.exists():
            return {'success': False, 'error': 'Klant niet gevonden'}
        return {'success': True, 'balance': partner.balance, 'name': partner.name}
