# -*- coding: utf-8 -*-
# © 2016 Jarsa Sistemas, S.A. de C.V.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import logging

from openerp import http
from openerp.http import request
from openerp.addons.payment_conekta.controllers.main import ConektaController

_logger = logging.getLogger(__name__)
try:
    import conekta
except (ImportError, IOError) as err:
    _logger.debug(err)


class ConektaOxxoController(ConektaController):

    def conekta_oxxo_validate_data(self, data):
        _logger.debug('DEBUG VALIDATE DATA')
        res = False
        tx_obj = request.env['payment.transaction']
        res = tx_obj.sudo().form_feedback(data, 'conekta_oxxo')
        _logger.debug('DEBUG VALIDATE DATA res %s', res)
        return res

    @http.route('/payment/conekta/oxxo/charge', type='json',
                auth='public', website=True)
    def charge_oxxo_create(self, **kwargs):
        payment_acquirer = request.env['payment.acquirer']
        conekta_acq = payment_acquirer.sudo().search(
            [('provider', '=', 'conekta')])
        _logger.debug('DEBUG OXXO BEFORE PRIVATE KEY %s', conekta_acq)
        conekta.api_key = conekta_acq.conekta_private_key
        conekta.api_version = '2.4.0'
        params = self.create_params('conekta_oxxo')
        try:
            _logger.debug('DEBUG BEFORE RESPONSE OXXO ORDER')
            response = conekta.Order.create(params)
            # TODO: Join conekta order id with order in Odoo
            _logger.debug('DEBUG RESPONSE OXXO ORDER %s', response)
        except conekta.ConektaError as error:
            _logger.debug('DEBUG CONEKTA ERROR %s, %s',
                          error.message, type(error.message))
            return error.message['message_to_purchaser']
        self.conekta_oxxo_validate_data(response)
        return True
