import httpx
import pytest
from app.llm.nim_client import NimClient,ProviderError

def test_bad_provider_output_cannot_become_tool_execution(seeded,monkeypatch):
    from app.config import get_settings
    get_settings().nvidia_api_key='fake-test-key'
    def fake(*args,**kwargs):
        return httpx.Response(200,json={'choices':[{'message':{'content':'not JSON'}}]},request=httpx.Request('POST','https://example.test'))
    monkeypatch.setattr('app.llm.nim_client.httpx.post',fake)
    with pytest.raises(ProviderError):NimClient().json_completion('system','user')

def test_missing_key_and_bounded_calls(seeded):
    from app.config import get_settings
    get_settings().nvidia_api_key=''
    client=NimClient()
    with pytest.raises(ProviderError):client.json_completion('system','user')
    assert client.calls==0
