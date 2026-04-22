# -*- coding: utf-8 -*-
{
    'name': 'Kassa POS',
    'version': '1.0',
    'category': 'Point of Sale',
    'summary': 'Custom POS module voor schoolproject',
    'description': """
        Custom Odoo POS Module
        ======================
        * POS functionaliteit voor kassa systeem
        * Testklant data
        * Integratie ready voor RabbitMQ API
    """,
    'author': 'Brend De Greef',
    'depends': [
        'base',
        'point_of_sale',
        'account',
        'sales_team',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/res_partner_data.xml',
        'data/user_contact_data.xml',
        'data/product_product_data.xml',
        'data/pos_config_data.xml',
        'views/kassa_pos_user_registration_view.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'kassa_pos/static/src/css/user_registration.css',
            'kassa_pos/static/src/js/UserRegistration.js',
            'kassa_pos/static/src/js/ProductScreenUserButton.js',
            'kassa_pos/static/src/js/BadgeScanner.js',
            'kassa_pos/static/src/js/ClosingButton.js',
        ],
    },
    'external_dependencies': {
        'python': ['pika'],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
}
