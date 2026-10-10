from app.security.authorization import owned_order, AccessDenied, DENIED

def lookup_order(db,customer_id,order_id):
    order=owned_order(db,customer_id,order_id)
    order.pop('delivery_note',None)
    order['items']=[dict(r) for r in db.execute('SELECT i.*,p.name,p.category FROM order_items i JOIN products p USING(sku) WHERE order_id=?',(order_id,))]
    return order

def find_items(db,customer_id,order_id=None,sku=None,product_text=None):
    if not customer_id:
        raise AccessDenied('Sign in through X-Customer-Id for personal questions.')
    if order_id:
        owned_order(db,customer_id,order_id)
    sql='''SELECT i.*,o.status,o.order_date,p.name,p.category,p.warranty_months,p.price,c.tier
    FROM order_items i JOIN orders o USING(order_id) JOIN products p USING(sku) JOIN customers c ON c.customer_id=o.customer_id
    WHERE o.customer_id=?'''
    args=[customer_id]
    if order_id:
        sql+=' AND i.order_id=?'; args.append(order_id)
    if sku:
        sql+=' AND i.sku=?';args.append(sku)
    if product_text:
        sql+=' AND (lower(p.name) LIKE ? OR lower(p.category) LIKE ?)'
        args.extend([f'%{product_text.lower()}%']*2)
    return [dict(row) for row in db.execute(sql,args)]
