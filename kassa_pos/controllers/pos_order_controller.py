from odoo import http
from odoo.http import request


class KassaPosOrderController(http.Controller):
    @http.route('/kassa_pos/get_gks_vat_breakdown', type='json', auth='user')
    def get_gks_vat_breakdown(self, order_id=None, **kwargs):
        """
        JSON RPC endpoint returning the server-side GKS VAT breakdown for a given pos.order id.
        Expects: {order_id: <int>}
        Returns: {'ok': True, 'breakdown': {...}} or {'ok': False, 'error': 'msg'}
        """
        try:
            if not order_id:
                return {'ok': False, 'error': 'missing_order_id'}

            order = request.env['pos.order'].sudo().browse(int(order_id))
            if not order or not order.exists():
                return {'ok': False, 'error': 'order_not_found'}

            breakdown = order._build_gks_vat_breakdown()
            return {'ok': True, 'breakdown': breakdown}
        except Exception as e:
            return {'ok': False, 'error': str(e)}
