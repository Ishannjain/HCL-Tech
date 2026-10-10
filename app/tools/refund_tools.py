from decimal import Decimal, ROUND_HALF_UP

def calculate_refund(ctx,item,reason,eligibility):
    if eligibility['result']!='ELIGIBLE':
        return {'result':'NOT_AVAILABLE','message':'A refund cannot be promised for an ineligible or unverified return.'}
    if eligibility.get('disposition')=='REPLACEMENT':
        return {'result':'REPLACEMENT_ONLY','message':'A replacement is available; a cash refund is not authorized by this policy condition.'}
    pct=ctx.rule('restocking_fee_pct',item,reason)
    shipping=ctx.rule('reverse_shipping_fee',item,reason)
    approval=ctx.rule('auto_refund_limit',item,reason)
    money=lambda v:Decimal(str(v)).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
    gross=money(Decimal(str(item['net_unit_price']))*item['qty'])
    fee=money(gross*Decimal(pct['value'])/100)
    reverse=money(shipping['value'])
    if fee+reverse>gross:
        return {'result':'NOT_AVAILABLE','message':'Fees exceed the paid amount; support review is required.'}
    amount=money(gross-fee-reverse)
    limit=Decimal(approval['value'])
    within={'<=':amount<=limit,'<':amount<limit,'=':amount<=limit,'>=':amount>=limit,'>':amount>limit}[approval['operator']]
    return {'result':'ESTIMATE','currency':'INR','gross_amount':float(gross),'restocking_fee':float(fee),
            'reverse_shipping_fee':float(reverse),'refund_amount':float(amount),'approval_required':not within,
            'money_issued':False,'rounding':'Decimal ROUND_HALF_UP to two places'}
