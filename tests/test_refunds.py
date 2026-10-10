from tests.conftest import ask

def eligibility(answer):
    return next(t['output'] for t in answer['tools_invoked'] if t['tool']=='check_return_eligibility')

def test_return_boundary(client):
    last=ask(client,'Can I return defective item O-100051 SKU-0001?')
    late=ask(client,'Can I return defective item O-100052 SKU-0001?')
    assert eligibility(last)['result']=='ELIGIBLE'
    assert eligibility(last)['days_since_delivery']==7
    assert eligibility(late)['result']=='INELIGIBLE'

def test_net_price_refund_and_approval(client):
    discounted=ask(client,'How much refund for defective item O-100058 SKU-0001?',customer='C1002')
    calc=next(t['output'] for t in discounted['tools_invoked'] if t['tool']=='calculate_refund')
    assert calc['gross_amount']==2100
    assert calc['refund_amount']==1830
    assert calc['money_issued'] is False
    high=ask(client,'How much refund for defective item O-100057 SKU-0004?')
    assert next(t['output'] for t in high['tools_invoked'] if t['tool']=='calculate_refund')['approval_required'] is True

def test_state_and_warranty(client):
    assert eligibility(ask(client,'Can I return defective item O-100060 SKU-0001?'))['result']=='INELIGIBLE'
    assert eligibility(ask(client,'Can I return defective item O-100050 SKU-0001?'))['result']=='ALREADY_REQUESTED'
    warranty=ask(client,'Is my item O-100055 SKU-0001 under warranty?')
    assert next(t['output'] for t in warranty['tools_invoked'] if t['tool']=='check_warranty')['result']=='EXPIRED'

def test_multistep_and_whatif(client):
    response=ask(client,'My defective item O-100052 SKU-0001: can I return it and if not use warranty?')
    assert {t['tool'] for t in response['tools_invoked']} >= {'check_return_eligibility','check_warranty'}
    hypo=ask(client,'What if I return my defective item O-100051 SKU-0001 after 9 days?')
    assert eligibility(hypo)['days_since_delivery']==9
    assert hypo['assumptions']

def test_idempotent_write(client):
    payload={'order_id':'O-100051','sku':'SKU-0001','reason':'DEFECTIVE','idempotency_key':'test-unique-key'}
    first=client.post('/returns',headers={'X-Customer-Id':'C1001'},json=payload)
    second=client.post('/returns',headers={'X-Customer-Id':'C1001'},json=payload)
    assert first.status_code==200,first.text
    assert first.json()==second.json()
    from app.database import connect
    with connect() as db:
        assert db.execute("SELECT COUNT(*) FROM returns WHERE order_id='O-100051'").fetchone()[0]==1

def test_write_authorization(client):
    payload={'order_id':'O-100051','sku':'SKU-0001','reason':'DEFECTIVE','idempotency_key':'bad-owner'}
    assert client.post('/returns',headers={'X-Customer-Id':'C1002'},json=payload).status_code==403
