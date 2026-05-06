# -*- coding: utf-8 -*-

from . import utils
from . import models
from . import controllers


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


