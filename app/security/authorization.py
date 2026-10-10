class AccessDenied(Exception):
    pass

DENIED = 'This order is not available to the authenticated customer.'

def owned_order(db, customer_id, order_id):
    if not customer_id:
        raise AccessDenied('Sign in through X-Customer-Id for personal questions.')
    row = db.execute('SELECT * FROM orders WHERE order_id=? AND customer_id=?', (order_id, customer_id)).fetchone()
    if not row:
        raise AccessDenied(DENIED)
    return dict(row)
