import re
from decimal import Decimal, InvalidOperation
from app.schemas.source import RuleInput

PARAMETERS = {
 'return_window_days':'integer','damage_report_hours':'integer','restocking_fee_pct':'decimal',
 'reverse_shipping_fee':'decimal','auto_refund_limit':'decimal','non_returnable':'boolean',
 'requires_quality_check':'boolean','requires_brand_certificate':'boolean',
 'replacement_first':'boolean','warranty_start':'enum','change_of_mind_allowed':'boolean',
}

def validate_rule(rule: RuleInput, meta, sections):
    if meta.authority_level == 5:
        raise ValueError('Untrusted level 5 sources cannot introduce authoritative rules')
    if rule.source_doc_id != meta.doc_id:
        raise ValueError('Rule source_doc_id does not match document')
    if rule.parameter not in PARAMETERS or rule.operator not in {'=','<=','<','>=','>'}:
        raise ValueError('Unsupported rule parameter or operator; no rule was activated')
    if rule.effective_from != meta.effective_from or rule.effective_to != meta.effective_to:
        raise ValueError('Rule dates must match source metadata')
    if rule.scope_categories.upper() != meta.scope_categories and meta.scope_categories != 'ALL':
        if not set(rule.scope_categories.upper().split(';')).issubset(set(meta.scope_categories.split(';'))):
            raise ValueError('Rule category scope exceeds document scope')
    if rule.scope_tiers.upper() != meta.scope_tiers and meta.scope_tiers != 'ALL':
        if not set(rule.scope_tiers.upper().split(';')).issubset(set(meta.scope_tiers.split(';'))):
            raise ValueError('Rule tier scope exceeds document scope')
    body = sections.get(rule.source_section)
    normalized = lambda t: re.sub(r'\s+',' ',t).strip().casefold()
    if not body or normalized(rule.evidence_quote) not in normalized(body):
        raise ValueError('Rule evidence does not occur in its cited section')
    kind = PARAMETERS[rule.parameter]
    if kind in {'integer','decimal'}:
        try:
            number = Decimal(rule.value)
        except InvalidOperation as exc:
            raise ValueError('Invalid numeric threshold') from exc
        if not number.is_finite() or number < 0 or (kind == 'integer' and number != number.to_integral_value()):
            raise ValueError('Threshold must be finite and nonnegative with the declared type')
        if rule.parameter == 'restocking_fee_pct' and number > 100:
            raise ValueError('Percentage above 100')
        numeric_evidence = {Decimal(n.replace(',','')) for n in re.findall(r'\d[\d,]*(?:\.\d+)?',rule.evidence_quote)}
        if number not in numeric_evidence:
            raise ValueError('Threshold is not present in evidence')
    if kind == 'boolean' and rule.value.lower() not in {'true','false'}:
        raise ValueError('Boolean rule must be true or false')
    if kind == 'enum' and rule.value not in {'delivery','purchase'}:
        raise ValueError('Unsupported warranty start')
    if set(rule.conditions) - {'reason'} or rule.conditions.get('reason','DEFECTIVE') not in {'DEFECTIVE','DAMAGED','WRONG_ITEM','CHANGED_MIND'}:
        raise ValueError('Unsupported rule condition')
    return rule
