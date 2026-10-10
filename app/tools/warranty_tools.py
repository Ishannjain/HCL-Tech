import calendar
from datetime import date

def add_months(start,months):
    index=start.year*12+start.month-1+months
    year,month=divmod(index,12)
    month+=1
    return date(year,month,min(start.day,calendar.monthrange(year,month)[1]))

def check_warranty(ctx,item):
    start_rule=ctx.rule('warranty_start',item)
    if item['warranty_months']==0:
        return {'result':'NO_WARRANTY','warranty_months':0}
    start=item['delivered_on'] if start_rule['value']=='delivery' else item['order_date']
    if not start:
        return {'result':'NOT_STARTED','message':'No delivery date is recorded.'}
    begin=date.fromisoformat(start)
    expiry=add_months(begin,item['warranty_months'])
    return {'result':'VALID' if begin<=ctx.as_of<=expiry else ('NOT_STARTED' if ctx.as_of<begin else 'EXPIRED'),
            'starts_on':str(begin),'expires_on':str(expiry),'warranty_months':item['warranty_months'],
            'message':'Recorded coverage period only; installation, exclusions, and claim verification still apply.'}
