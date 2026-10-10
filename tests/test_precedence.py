from tests.conftest import ask
from app.rules.precedence import choose,RuleConflict
import pytest

def candidate(id,value,authority=1,effective='2026-01-01',supersedes='',section='1'):
    return {'rule_id':id,'value':value,'operator':'<=','effective_from':effective,'source_section':section,
        'source':{'doc_id':id,'authority_level':authority,'supersedes':supersedes}}

def test_annex_a_steps():
    base=candidate('BASE','10')
    faq=candidate('FAQ','15',4,'2026-09-01')
    assert choose([base,faq],'return_window_days')[0]['rule_id']=='BASE'
    circular=candidate('CIRC','7',2,'2026-08-01','BASE#1')
    assert choose([base,circular,faq],'return_window_days')[0]['rule_id']=='CIRC'
    newer=candidate('NEW','5',1,'2026-09-01')
    assert choose([base,newer],'return_window_days')[0]['rule_id']=='NEW'
    with pytest.raises(RuleConflict):choose([base,candidate('TIE','8')],'return_window_days')

def test_lower_authority_supersession_rejected():
    assert choose([candidate('BASE','10'),candidate('NOTICE','3',3,supersedes='BASE')],'window')[0]['rule_id']=='BASE'

def test_synthetic_circular_overrides_faq(client):
    answer=ask(client,'What is the return window for AUDIO?',customer=None)
    assert answer['applied_rules'][0]['value']=='5'
    assert answer['citations'][0]['doc_id']=='DEMO-CIRCULAR'
    assert answer['conflicts_detected']

def test_historical_snapshot_not_misrepresented(client):
    answer=ask(client,'What is the return window for laptops?',customer=None,as_of='2026-10-09')
    assert answer['answer_type']=='not_found'

def test_scope_and_inclusive_effective_dates():
    from app.rules.precedence import applicable
    meta={'effective_from':'2026-10-10','effective_to':'2026-10-12','scope_categories':'LAPTOP','scope_tiers':'GOLD'}
    assert applicable(meta,'2026-10-10','LAPTOP','GOLD')
    assert applicable(meta,'2026-10-12','LAPTOP','GOLD')
    assert not applicable(meta,'2026-10-13','LAPTOP','GOLD')
    assert not applicable(meta,'2026-10-10','AUDIO','GOLD')
    assert not applicable(meta,'2026-10-10','LAPTOP','STANDARD')
