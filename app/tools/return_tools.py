import hashlib
import json
import uuid
from datetime import date
from app.tools.order_tools import find_items
from app.rules.precedence import RuleMissing

def check_return_eligibility(ctx,item,reason):
    if reason not in {'DEFECTIVE','DAMAGED','WRONG_ITEM','CHANGED_MIND'}:
        return {'result':'CLARIFICATION_NEEDED','message':'State the reason: defective, damaged, wrong item, or changed mind.'}
    if item['status']!='DELIVERED' or not item['delivered_on']:
        return {'result':'INELIGIBLE','message':'The item has not been delivered.'}
    if date.fromisoformat(item['delivered_on'])>ctx.as_of:
        return {'result':'INELIGIBLE','message':'The item was not delivered by the scenario date.'}
    if ctx.db.execute("SELECT 1 FROM returns WHERE order_id=? AND sku=? AND status!='REJECTED'",(item['order_id'],item['sku'])).fetchone():
        return {'result':'ALREADY_REQUESTED','message':'An active or completed return already exists for this item.'}
    try:
        nonreturn=ctx.rule('non_returnable',item,reason)
        if nonreturn['value']=='true':
            return {'result':'INELIGIBLE','message':'This category is non-returnable under the applicable clause.'}
    except RuleMissing:
        pass
    if reason=='CHANGED_MIND':
        rule=ctx.rule('change_of_mind_allowed',item,reason)
        if rule['value']=='false':
            return {'result':'INELIGIBLE','message':'The applicable policy does not permit this change-of-mind return.'}
    window=ctx.rule('return_window_days',item,reason)
    elapsed=(ctx.as_of-date.fromisoformat(item['delivered_on'])).days
    compare={'<=':lambda a,b:a<=b,'<':lambda a,b:a<b,'=':lambda a,b:a<=b,'>=':lambda a,b:a>=b,'>':lambda a,b:a>b}[window['operator']]
    if not compare(elapsed,int(window['value'])):
        return {'result':'INELIGIBLE','message':'The return window has closed.','days_since_delivery':elapsed,'window_days':int(window['value'])}
    facts_raw=ctx.db.execute('SELECT facts FROM order_facts WHERE order_id=? AND sku=?',(item['order_id'],item['sku'])).fetchone()
    facts=json.loads(facts_raw['facts']) if facts_raw else {}
    if reason=='DAMAGED':
        if facts.get('activated') is None:
            return {'result':'CLARIFICATION_NEEDED','message':'Support must verify whether the item was activated or used.'}
        if facts['activated']:
            return {'result':'INELIGIBLE','message':'The source excludes damaged items already used or activated.'}
        try:
            hours=ctx.rule('damage_report_hours',item,reason)
            return {'result':'CLARIFICATION_NEEDED','message':f"Damage must be reported within {hours['value']} hours; delivery and reporting timestamps require support verification."}
        except RuleMissing:
            pass
    for parameter,fact in [('requires_quality_check','qc_passed'),('requires_brand_certificate','brand_certified')]:
        if parameter=='requires_brand_certificate' and reason!='DEFECTIVE':
            continue
        requirement=ctx.rule(parameter,item,reason)
        if requirement['value']=='true' and facts.get(fact) is not True:
            return {'result':'CLARIFICATION_NEEDED','message':f'Support verification required: {fact}.'}
    replacement=ctx.rule('replacement_first',item,reason)
    disposition='REFUND'
    if reason in {'DEFECTIVE','DAMAGED'} and replacement['value']=='true':
        if 'inventory_available' not in facts:
            return {'result':'CLARIFICATION_NEEDED','message':'Support must verify replacement inventory before promising a refund.'}
        disposition='REPLACEMENT' if facts['inventory_available'] else 'REFUND'
    return {'result':'ELIGIBLE','disposition':disposition,'days_since_delivery':elapsed,'window_days':int(window['value'])}

def create_return(ctx,order_id,sku,reason,idempotency_key):
    ctx.db.execute('BEGIN IMMEDIATE')
    fingerprint=hashlib.sha256(json.dumps([order_id,sku,reason]).encode()).hexdigest()
    existing=ctx.db.execute('SELECT * FROM return_operations WHERE customer_id=? AND idempotency_key=?',(ctx.customer_id,idempotency_key)).fetchone()
    if existing:
        if existing['fingerprint']!=fingerprint:
            raise ValueError('Idempotency key was already used with different inputs')
        return json.loads(existing['result'])
    items=find_items(ctx.db,ctx.customer_id,order_id,sku)
    if not items:
        from app.security.authorization import AccessDenied,DENIED
        raise AccessDenied(DENIED)
    eligibility=check_return_eligibility(ctx,items[0],reason)
    if eligibility['result']!='ELIGIBLE':
        return eligibility
    from app.tools.refund_tools import calculate_refund
    refund=calculate_refund(ctx,items[0],reason,eligibility)
    return_id=f'R-{uuid.uuid4().hex[:12]}'
    ctx.db.execute('INSERT INTO returns VALUES (?,?,?,?,?,?,?)',(return_id,order_id,sku,str(ctx.as_of),reason,'REQUESTED',0))
    result={'return_id':return_id,'status':'REQUESTED','eligibility':eligibility,'refund_estimate':refund,'money_issued':False}
    if refund.get('approval_required'):
        ctx.db.execute('INSERT INTO approvals VALUES (?,?,?)',(uuid.uuid4().hex,return_id,'PENDING'))
        result['approval_status']='PENDING'
    ctx.db.execute('INSERT INTO return_operations VALUES (?,?,?,?)',(ctx.customer_id,idempotency_key,fingerprint,json.dumps(result)))
    return result
