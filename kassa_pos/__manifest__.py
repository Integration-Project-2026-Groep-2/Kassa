# -*- coding: utf-8 -*-
{
    'name': 'Kassa POS',
    'version': '1.2',
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
        'data/pos_config_data.xml',
        'data/pos_config_main_data.xml',
        'data/res_partner_data.xml',
        'data/user_contact_data.xml',
        'data/product_product_data.xml',
        'views/kassa_pos_user_registration_view.xml',
        'views/pos_order_batch_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'kassa_pos/static/src/css/user_registration.css',
            'kassa_pos/static/src/css/gks_receipt.css',
            'kassa_pos/static/src/css/qr_scanner.css',
            'kassa_pos/static/src/js/UserRegistration.js',
            'kassa_pos/static/src/js/gks_receipt.js',
            'kassa_pos/static/src/js/ProductScreenUserButton.js',
            'kassa_pos/static/src/js/BadgeScanner.js',
            'kassa_pos/static/src/js/ClosingButton.js',
            'kassa_pos/static/src/js/BalanceValidation.js',
            'kassa_pos/static/src/js/BalanceTopupModal.js',
            'kassa_pos/static/src/js/BalanceButton.js',
            'kassa_pos/static/src/js/QrScannerButton.js',
            'kassa_pos/static/src/xml/gks_receipt.xml',
        ],
    },
    'external_dependencies': {
        'python': ['pika'],
    },
    'post_init_hook': 'post_init',
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
}
