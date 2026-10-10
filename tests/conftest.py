import pytest

@pytest.fixture
def seeded(tmp_path,monkeypatch):
    monkeypatch.setenv('RUNTIME_DIR',str(tmp_path/'runtime'))
    monkeypatch.setenv('MOCK_LLM','true')
    monkeypatch.setenv('RETRIEVAL_BACKEND','keyword')
    monkeypatch.setenv('ADMIN_API_KEY','test-admin-key')
    from app.config import get_settings
    get_settings.cache_clear()
    from scripts.bootstrap import bootstrap
    bootstrap()
    from datetime import date
    monkeypatch.setattr('app.main.today',lambda:date(2026,10,10))
    yield
    get_settings.cache_clear()

@pytest.fixture
def client(seeded):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:yield client

def ask(client,question,customer='C1001',as_of='2026-10-10'):
    response=client.post('/ask',headers={'X-Customer-Id':customer} if customer else {},json={'question':question,'as_of_date':as_of})
    assert response.status_code==200,response.text
    return response.json()
