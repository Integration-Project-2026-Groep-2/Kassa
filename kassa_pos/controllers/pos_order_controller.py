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

    @http.route('/kassa_pos/get_vsc_code', type='json', auth='user')
    def get_vsc_code(self, order_id=None, **kwargs):
        """
        JSON RPC endpoint returning the VSC code for a given pos.order id.
        Expects: {order_id: <int>}
        Returns: {'vsc_code': '...'} or {'error': 'msg'}
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info("kassa_pos.get_vsc_code called with order_id=%s kwargs=%s", order_id, kwargs)
            
            if not order_id:
                logger.warning("kassa_pos.get_vsc_code: missing_order_id")
                return {'ok': False, 'error': 'missing_order_id'}

            order = request.env['pos.order'].sudo().browse(int(order_id))
            if not order or not order.exists():
                logger.warning("kassa_pos.get_vsc_code: order_not_found for id=%s", order_id)
                return {'ok': False, 'error': 'order_not_found'}

            vsc_code = order._build_vsc_code()
            logger.info("kassa_pos.get_vsc_code: successfully built vsc=%s for order_id=%s", vsc_code, order_id)
            return {'ok': True, 'vsc_code': vsc_code}
        except Exception as e:
            logger.exception("kassa_pos.get_vsc_code: exception for order_id=%s: %s", order_id, str(e))
            return {'ok': False, 'error': str(e)}
