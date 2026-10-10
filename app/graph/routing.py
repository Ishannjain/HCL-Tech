import re
from pydantic import BaseModel, ConfigDict
from typing import Literal

class Plan(BaseModel):
    model_config=ConfigDict(extra='forbid')
    intent: Literal['policy','order','return','refund','warranty','multistep']='policy'
    order_id: str | None=None
    sku: str | None=None
    reason: Literal['DEFECTIVE','DAMAGED','WRONG_ITEM','CHANGED_MIND'] | None=None
    product_text: str | None=None

def route(question):
    q=question.lower()
    order=re.search(r'\bO-\d{6}\b',question,re.I)
    sku=re.search(r'\bSKU-[\w-]+\b',question,re.I)
    personal=bool(order or sku or re.search(r'\b(my|mine|i|me)\b',q))
    if not order and not sku and re.search(r'how (?:do|can|should) (?:i|we)|how to',q) and (not re.search(r'\bmy\b',q) or re.search(r'\bclaim|prepare|pack|procedure|steps\b',q)):
        personal=False
    intent='policy'
    returning=bool(re.search(r'return|send back|replacement|exchange',q))
    warranty=bool(re.search(r'warranty|guarantee|stopped working',q))
    refund=bool(re.search(r'refund|money back',q))
    if personal:
        if (returning and warranty) or ('if not' in q and returning):intent='multistep'
        elif refund:intent='refund'
        elif returning:intent='return'
        elif warranty:intent='warranty'
        elif order or re.search(r'order|delivery|track|shipped',q):intent='order'
    reason=None
    if re.search(r'wrong[ -](?:item|product)',q):reason='WRONG_ITEM'
    elif re.search(r'damaged|broken on arrival',q):reason='DAMAGED'
    elif re.search(r'defective|stopped working|faulty',q):reason='DEFECTIVE'
    elif re.search(r'changed? (?:my )?mind|change of mind',q):reason='CHANGED_MIND'
    return Plan(intent=intent,order_id=order.group().upper() if order else None,sku=sku.group().upper() if sku else None,reason=reason)
