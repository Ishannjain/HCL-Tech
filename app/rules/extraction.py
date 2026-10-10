import re
from app.schemas.source import RuleInput

def extract_explicit_rules(chunks, meta):
    """Bounded grammar for unambiguous numeric rules; unsupported prose stays explicit."""
    patterns = [
        ('return_window_days',r'(?:return|replacement)(?:\s+window)?[^.\n]{0,60}?\b(\d+)\s*(?:calendar\s+)?days?\b','<='),
        ('restocking_fee_pct',r'restocking[^.\n]{0,40}?\b(\d+(?:\.\d+)?)\s*%','='),
        ('reverse_shipping_fee',r'reverse[ -]shipping[^.\n]{0,40}?(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d+)?)','='),
        ('auto_refund_limit',r'(?:auto(?:matic)?[ -]refund\s+(?:limit|approval\s+limit)|human[ -]approval\s+limit)[^.\n]{0,30}?(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d+)?)','<='),
    ]
    rules = []
    for chunk in chunks:
        for line in chunk['text'].splitlines():
            if re.search(r'ignore\s+(?:all\s+)?(?:previous|prior)|system\s+prompt|call\s+(?:the\s+)?tool',line,re.I):
                continue
            for param,pattern,operator in patterns:
                match = re.search(pattern,line,re.I)
                if match:
                    rules.append(RuleInput(rule_id=f'{meta.doc_id}-{param}-{len(rules)+1}',description=line.strip(),
                        parameter=param,operator=operator,value=match.group(1).replace(',',''),
                        scope_categories=meta.scope_categories,scope_tiers=meta.scope_tiers,
                        effective_from=meta.effective_from,effective_to=meta.effective_to,
                        source_doc_id=meta.doc_id,source_section=chunk['section'],evidence_quote=line.strip()))
    return rules
