# -*- coding: utf-8 -*-
# © 2016 Jarsa Sistemas, S.A. de C.V.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import logging

from openerp import http, _
from openerp.http import request
from datetime import datetime
from time import mktime
_logger = logging.getLogger(__name__)
try:
    import conekta
except (ImportError, IOError) as err:
    _logger.debug(err)


class ConektaController(http.Controller):

    def conekta_validate_data(self, data):
        res = False
        tx_obj = request.env['payment.transaction']
        res = tx_obj.sudo().form_feedback(data, 'conekta')
        return res

    def conekta_create_customer(self, customer_id, conekta_customer_data):
        conekta_customer = conekta.Customer.create(conekta_customer_data)
        _logger.debug('DEBUG CONEKTA CUSTOMER ID %s', conekta_customer)
        _logger.debug('DEBUG CONEKTA CUSTOMER ID %s', type(conekta_customer))
        if conekta_customer:
            _logger.debug('DEBUG CONEKTA CUSTOMER ID %s',
                          conekta_customer['id'])
            ResPartner = request.env['res.partner']
            ResPartner.browse(customer_id).write(
                {'conekta_customer_id': conekta_customer['id']})
            return conekta_customer['id']

        return False

    def create_params(self, acquirer):
        so_id = request.session['sale_order_id']
        so = request.env['sale.order'].sudo().search([('id', '=', so_id)])
        _logger.debug('DEBUG SALE ORDER %s', so)

        if not so.partner_id.conekta_customer_id:
            customer_data = dict()
            customer_data['name'] = so.partner_id.name
            customer_data['phone'] = so.partner_id.phone
            customer_data['email'] = so.partner_id.email

            customer_shipping_addresses = so.partner_id.child_ids.filtered(
                lambda contact: contact.type == 'delivery'
            )

            if customer_shipping_addresses:
                customer_data['shipping_contacts'] = list()

                for delivery_address in customer_shipping_addresses:
                    _logger.debug('DEBUG SHIPPING CONTACTS PHONE %s, %s',
                                  delivery_address.phone, type(delivery_address.phone))

                    customer_data['shipping_contacts'].append({
                        "phone": delivery_address.phone,
                        "receiver": delivery_address.name,
                        "address": {
                            "street1": delivery_address.street,
                            "street2": delivery_address.street2,
                            "city": delivery_address.city,
                            "state": delivery_address.state_id,
                            "country": delivery_address.country_id.code,
                            "postal_code": delivery_address.zip,
                        }
                    })

            customer_id = self.conekta_create_customer(
                so.partner_id.id, customer_data)

        else:

            customer_id = so.partner_id.conekta_customer_id

        params = {}
        params['customer_info'] = dict()
        params['customer_info']['customer_id'] = customer_id
        params['metadata'] = dict()
        params['metadata']['description'] = _(
            '%s Order %s' % (so.company_id.name, so.name)
        )
        params['metadata']['reference'] = so.name
        _logger.debug('DEBUG CURRENCY SALE ORDER %s', so.currency_id.name)
        params['currency'] = so.currency_id.name

        params['line_items'] = []
        for order_line in so.order_line:

            if order_line.is_delivery:
                continue

            item = {}
            item['name'] = order_line.product_id.name
            _logger.debug('DEBUG ITEM DESCRIPTION %s, %s', item[
                          'name'], order_line.product_id.description_sale)

            if order_line.product_id.description_sale:
                item['description'] = order_line.product_id.description_sale

            item['unit_price'] = int(order_line.price_unit * 100)
            item['quantity'] = int(order_line.product_uom_qty)
            item['sku'] = order_line.product_id.default_code
            item['category'] = order_line.product_id.categ_id.name
            params['line_items'].append(item)

        shipping_lines = so.order_line.filtered(
            lambda line: line.is_delivery)

        if shipping_lines:

            params['shipping_lines'] = list()

            for shipping_line in shipping_lines:

                params['shipping_lines'].append({
                    'amount': int(shipping_line.price_unit * 100),
                    'carrier': shipping_line.order_id.carrier_id.partner_id.name,
                })

        if so.partner_shipping_id:

            params['shipping_contact'] = dict()
            _logger.debug('DEBUG SHIPPING CONTACT PHONE %s, %s',
                          so.partner_shipping_id.phone, type(so.partner_shipping_id.phone))

            params['shipping_contact']["phone"] = so.partner_shipping_id.phone
            _logger.debug('DEBUG SHIPPING CONTACT PHONE 2 %s, %s',
                          params['shipping_contact']["phone"], type(params['shipping_contact']["phone"]))
            _logger.debug('DEBUG RECEIVER %s', so.partner_shipping_id.name)
            params['shipping_contact'][
                "receiver"] = so.partner_shipping_id.name + ' test'
            params['shipping_contact']['address'] = {
                'street1': so.partner_shipping_id.street,
                "street2": so.partner_shipping_id.street2,
                'postal_code': so.partner_shipping_id.zip,
                'country': so.partner_shipping_id.country_id.code,
                "city": so.partner_shipping_id.city,
                "state": so.partner_shipping_id.state_id.name,
            }

        taxes = so.mapped('order_line.tax_id')

        if taxes:

            AccountInvoiceTax = request.env['account.invoice.tax']
            params['tax_lines'] = list()

            if len(taxes) == 1:

                account_invoice_tax = AccountInvoiceTax.search([
                    ('name', '=', taxes.name)])

                if account_invoice_tax:

                    try:
                        params['tax_lines'].append({
                            'description': account_invoice_tax[0].name2,
                            'amount': int(so.amount_tax * 100),
                        })

                    except:
                        _logger.debug('The tax doesn not exist')
                        pass
            # TODO: Consider also orders that have more than one tax.

        params['charges'] = [{
            'status': 'pending_payment',
            'payment_method': dict(),
        }]

        if acquirer == 'conekta':
            params['card'] = request.session['conekta_token']

        if acquirer == 'conekta_oxxo':
            params['charges'][0]['payment_method']['type'] = 'oxxo_cash'
        _logger.debug('DEBUG PARAMS %s', params)
        return params

    @http.route('/payment/conekta/charge', type='json',
                auth='public', website=True)
    def charge_create(self, token):
        request.session['conekta_token'] = token
        payment_acquirer = request.env['payment.acquirer']
        conekta_acq = payment_acquirer.sudo().search(
            [('provider', '=', 'conekta')])
        conekta.api_key = conekta_acq.conekta_private_key
        params = self.create_params('conekta')

        try:
            response = conekta.Charge.create(params)

        except conekta.ConektaError as error:
            return error.message['message_to_purchaser']
        self.conekta_validate_data(response)

        return True
