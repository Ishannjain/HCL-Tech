import hashlib
import time

def signin(client,username='customer1',password='Customer1@123'):
    return client.post('/auth/login',json={'username':username,'password':password})

def test_two_accounts_and_wrong_password(client):
    for username,password,identity in [('customer1','Customer1@123','C1001'),('customer2','Customer2@123','C1002')]:
        response=signin(client,username,password)
        assert response.status_code==200
        assert response.json()['customer_id']==identity
        assert 'password' not in response.json()
    assert signin(client,password='wrong').status_code==401
    assert signin(client,username='unknown',password='wrong').json()==signin(client,password='wrong').json()

def test_session_identity_and_cross_customer(client):
    token=signin(client).json()['access_token']
    headers={'Authorization':'Bearer '+token}
    assert client.get('/auth/me',headers=headers).json()=={'customer_id':'C1001'}
    body={'question':'Where is my order O-100058?','as_of_date':'2026-10-10'}
    response=client.post('/ask',headers=headers,json=body)
    assert response.json()['answer_type']=='refused'
    assert client.post('/ask',headers=dict(headers,**{'X-Customer-Id':'C1002'}),json=body).status_code==403
    assert client.get('/audit/unknown',headers=dict(headers,**{'X-Customer-Id':'C1002'})).status_code==403
    assert client.post('/returns',headers=dict(headers,**{'X-Customer-Id':'C1002'}),json={'order_id':'O-100058','sku':'SKU-0001','reason':'DEFECTIVE','idempotency_key':'test-login-key'}).status_code==403

def test_logout_revokes_session_and_expiry(client):
    token=signin(client).json()['access_token'];headers={'Authorization':'Bearer '+token}
    assert client.post('/auth/logout',headers=headers).status_code==200
    assert client.get('/auth/me',headers=headers).status_code==401
    token=signin(client).json()['access_token']
    from app.database import connect
    with connect() as db:
        db.execute('UPDATE login_sessions SET expires_at=? WHERE token_hash=?',(int(time.time())-1,hashlib.sha256(token.encode()).hexdigest()))
        assert db.execute('SELECT password_hash FROM login_accounts LIMIT 1').fetchone()[0] not in ['Customer1@123','Customer2@123']
    assert client.get('/auth/me',headers={'Authorization':'Bearer '+token}).status_code==401
    assert client.get('/auth/me',headers={'Authorization':'Bearer invalid'}).status_code==401
