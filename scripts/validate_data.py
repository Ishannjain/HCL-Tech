import argparse
import csv
import json
import re
from datetime import date
from pathlib import Path
from decimal import Decimal, InvalidOperation

FIELDS={
 'customers':['customer_id','full_name','tier','city','joined_year'],
 'products':['sku','name','category','price','warranty_months'],
 'orders':['order_id','customer_id','order_date','status','payment_method','delivery_note'],
 'order_items':['order_id','sku','qty','net_unit_price','delivered_on'],
 'returns':['return_id','order_id','sku','requested_on','reason','status','refund_amount'],
}

def read_data(directory):
    data={}
    for table,fields in FIELDS.items():
        file=Path(directory)/f'{table}.csv'
        if not file.exists():
            raise ValueError(f'Missing {file.name}')
        with file.open(encoding='utf-8-sig',newline='') as stream:
            reader=csv.DictReader(stream)
            missing=set(fields)-set(reader.fieldnames or [])
            if missing:raise ValueError(f'{table}: missing columns {sorted(missing)}')
            data[table]=[{k:r[k] for k in fields} for r in reader]
    return data

def validate(data,allow_judge=False):
    errors=[]
    customers={r['customer_id']:r for r in data['customers']}
    products={r['sku']:r for r in data['products']}
    orders={r['order_id']:r for r in data['orders']}
    items={(r['order_id'],r['sku']):r for r in data['order_items']}
    keys={'customers':['customer_id'],'products':['sku'],'orders':['order_id'],'order_items':['order_id','sku'],'returns':['return_id']}
    for table,rows in data.items():
        found=set()
        for index,row in enumerate(rows):
            tag=f'{table} row {index+2}'
            key=tuple(row[k] for k in keys[table])
            if key in found:errors.append(f'{tag}: duplicate key')
            found.add(key)
            try:
                if table=='customers':
                    if not re.fullmatch(r'C\d{4}',row['customer_id']):raise ValueError('invalid customer ID')
                    if not allow_judge and int(row['customer_id'][1:])>=9000:raise ValueError('reserved customer ID')
                    if row['tier'] not in {'STANDARD','GOLD','PLATINUM'}:raise ValueError('invalid tier')
                    if not row['full_name'] or not row['city']:raise ValueError('empty name or city')
                    if not 1900<=int(row['joined_year'])<=2100:raise ValueError('invalid joined year')
                elif table=='products':
                    if not row['sku'].startswith('SKU-'):raise ValueError('invalid SKU')
                    if not allow_judge and row['sku'].startswith('SKU-JDG'):raise ValueError('reserved SKU')
                    price=Decimal(row['price'])
                    if not price.is_finite() or price<=0 or int(row['warranty_months'])<0:raise ValueError('invalid product values')
                elif table=='orders':
                    if not re.fullmatch(r'O-\d{6}',row['order_id']):raise ValueError('invalid order ID')
                    if not allow_judge and int(row['order_id'][2:])>=900000:raise ValueError('reserved order ID')
                    if row['customer_id'] not in customers:raise ValueError('missing customer')
                    date.fromisoformat(row['order_date'])
                    if row['status'] not in {'PLACED','SHIPPED','DELIVERED','CANCELLED'}:raise ValueError('invalid status')
                    if row['payment_method'] not in {'UPI','CARD','COD'}:raise ValueError('invalid payment method')
                elif table=='order_items':
                    if row['order_id'] not in orders or row['sku'] not in products:raise ValueError('missing order or product')
                    if int(row['qty'])<1:raise ValueError('qty below one')
                    paid=Decimal(row['net_unit_price'])
                    if not paid.is_finite() or not 0<paid<=Decimal(products[row['sku']]['price']):raise ValueError('invalid net price')
                    order=orders[row['order_id']]
                    if order['status']=='DELIVERED' and not row['delivered_on']:raise ValueError('delivered order needs delivered_on')
                    if row['delivered_on']:
                        if order['status']!='DELIVERED':raise ValueError('delivered_on for undelivered order')
                        if date.fromisoformat(row['delivered_on'])<date.fromisoformat(order['order_date']):raise ValueError('delivery before order')
                elif table=='returns':
                    if (row['order_id'],row['sku']) not in items:raise ValueError('missing composite item reference')
                    if date.fromisoformat(row['requested_on'])<date.fromisoformat(orders[row['order_id']]['order_date']):raise ValueError('return request before order')
                    if row['reason'] not in {'DEFECTIVE','DAMAGED','WRONG_ITEM','CHANGED_MIND'}:raise ValueError('invalid reason')
                    if row['status'] not in {'REQUESTED','PICKED_UP','REFUNDED','REJECTED'}:raise ValueError('invalid return status')
                    amount=Decimal(row['refund_amount'])
                    if not amount.is_finite() or amount<0:raise ValueError('invalid refund amount')
            except (ValueError,KeyError,InvalidOperation) as exc:
                errors.append(f'{tag}: {exc}')
    return errors

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dir',required=True,type=Path)
    parser.add_argument('--allow-judge',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:
        data=read_data(args.dir)
        result={'counts':{k:len(v) for k,v in data.items()},'violations':validate(data,args.allow_judge)}
    except ValueError as exc:result={'violations':[str(exc)]}
    output=json.dumps(result,indent=2)
    print(output)
    if args.output:args.output.write_text(output,encoding='utf-8')
    return bool(result['violations'])

if __name__=='__main__':raise SystemExit(main())
