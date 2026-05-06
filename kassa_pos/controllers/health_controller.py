# -*- coding: utf-8 -*-

from odoo import http


class HealthController(http.Controller):

    @http.route('/health', type='http', auth='public', csrf=False, save_session=False)
    def health(self, **kwargs):
        return http.Response('ok', status=200, content_type='text/plain; charset=utf-8')