# -*- coding: utf-8 -*-
# Copyright 2018 Humanytek - Manuel Marquez <manuel@humanytek.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from openerp import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    conekta_customer_id = fields.Char('Customer ID in Conekta')
