from tests.conftest import ask

def test_contract_and_health(client):
    answer=ask(client,'What is the return window for laptops?',customer=None)
    assert answer['answer_type']=='retrieved_fact'
    assert set(['trace_id','answer','citations','tools_invoked','applied_rules','conflicts_detected','assumptions','explanation','as_of_date'])<=set(answer)
    assert answer['applied_rules'][0]['value']=='7'
    assert client.get('/health').json()['sqlite']=='ready'
    assert len(client.get('/sources').json())==6

def test_invalid_input(client):
    assert client.post('/ask',json={'question':'','as_of_date':'bad'}).status_code==422
    assert client.post('/ask',json={'question':'hi','customer_id':'C1002'}).status_code==422

def test_absent_evidence(client):
    for question in ['Do you deliver to Antarctica?','Can I buy a submarine?','Do you accept cryptocurrency payments?']:
        answer=ask(client,question,customer=None)
        assert answer['answer_type']=='not_found'
        assert answer['answer']=='I could not find this information in the authorised sources.'

def test_clarification(client):
    assert ask(client,'Can I return my laptop?')['answer_type']=='clarification_needed'
    assert ask(client,'Can I return my item O-100051 SKU-0001?')['answer_type']=='clarification_needed'

def test_general_procedure_does_not_access_orders(client):
    for question in ['How do I raise a warranty claim?', 'How should I prepare a product for return?', 'How do I claim my warranty?']:
        answer=ask(client,question,customer=None)
        assert answer['answer_type'] in {'retrieved_fact','not_found'}
        assert not answer['tools_invoked']

def test_order_lookup(client):
    response=ask(client,'Where is my order O-100051?')
    assert response['answer_type']=='calculated'
    assert response['tools_invoked'][0]['tool']=='lookup_order'
    assert 'delivery_note' not in response['tools_invoked'][0]['output']
