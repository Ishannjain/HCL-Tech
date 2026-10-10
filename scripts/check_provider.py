"""Probe the configured NIM without logging credentials or model reasoning."""
import json
from app.llm.nim_client import NimClient

if __name__=='__main__':
    client=NimClient()
    result=client.json_completion('Return ONLY JSON {"status":"ok"}.','Connection test')
    if result.get('status')!='ok':raise ValueError('Provider response did not match the connection-test schema')
    print(json.dumps({'status':'ok','model':client.settings.nvidia_model,'calls':client.calls,'tokens':client.tokens}))
