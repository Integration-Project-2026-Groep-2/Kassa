from datetime import datetime

def make_product(category_name):
    class Categ:
        def __init__(self, name):
            self.name = name
    class Prod:
        def __init__(self, name, categ_name=None):
            self.name = name
            self.categ_id = Categ(categ_name) if categ_name else None
    return Prod('TestProduct', category_name)


def test_get_tax_rate_and_vat_breakdown_and_vsc():
    from kassa_pos.models.pos_order import PosOrder

    order = PosOrder()
    order.id = 11
    order.amount_total = 12.0
    order.date_order = datetime.utcnow()

    # Test tax mapping
    assert order._get_tax_rate_for_product(None) == 21.0
    assert order._get_tax_rate_for_product(make_product('food')) == 6.0
    assert order._get_tax_rate_for_product(make_product('drinks')) == 21.0

    # Create lines with product and tax_ids
    class Line:
        def __init__(self, qty, price_unit, product=None, tax_amount=None):
            self.qty = qty
            self.price_unit = price_unit
            self.product_id = product
            if tax_amount is not None:
                class T: pass
                t = T()
                t.amount = tax_amount
                self.tax_ids = [t]
            else:
                self.tax_ids = []

    # Line with explicit tax 6%
    l1 = Line(qty=2, price_unit=5.0, product=make_product('food'), tax_amount=6.0)
    order.lines = [l1]
    breakdown = order._build_gks_vat_breakdown()
    assert breakdown['gross_total'] == 10.0
    assert 6 in breakdown['rates']

    # VSC code length
    vsc = order._build_vsc_code()
    assert isinstance(vsc, str) and len(vsc) == 20


def test_build_payment_and_invoice_payloads():
    from kassa_pos.models.pos_order import PosOrder

    order = PosOrder()
    order.id = 7
    order.order_id_custom = 'ord-7'
    order.amount_total = 42.0
    order.date_order = datetime.utcnow()

    class Partner:
        def __init__(self):
            self.user_id_custom = 'u-1'
            self.email = 'p@example.com'
            self.name = 'Alice Smith'
            self.role = 'Customer'
            self.company_id_custom = ''
            self.badge_code = 'B1'

    order.partner_id = Partner()
    data = order._build_payment_confirmed_data()
    assert data['email'] == 'p@example.com'

    # invoice requested
    class LineObj:
        def __init__(self):
            class Prod: pass
            self.product_id = type('P', (), {'name': 'X'})
            self.qty = 1
            self.price_unit = 3.5

    order.lines = [LineObj()]
    inv = order._build_invoice_requested_data()
    assert inv['orderId'] == 'ord-7'
    assert inv['user']['firstName'] == 'Alice'
