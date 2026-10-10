import json
import time
import httpx
from app.config import get_settings

class ProviderError(Exception):
    pass

class NimClient:
    def __init__(self):
        self.settings=get_settings()
        self.calls=0
        self.tokens=0
        self.provider_errors=[]

    def json_completion(self,system,user,max_tokens=1600):
        if not self.settings.nvidia_api_key:
            raise ProviderError('NVIDIA_API_KEY is not configured')
        payload={'model':self.settings.nvidia_model,'messages':[{'role':'system','content':system},{'role':'user','content':user}],
                 'temperature':0.1,'max_tokens':max_tokens,'stream':False,'reasoning_effort':'none'}
        for attempt in range(2):
            self.calls+=1
            try:
                response=httpx.post(self.settings.nvidia_base_url.rstrip('/')+'/chat/completions',
                    headers={'Authorization':'Bearer '+self.settings.nvidia_api_key},json=payload,timeout=self.settings.llm_timeout_seconds)
                if response.status_code in {429,500,502,503,504} and attempt==0:
                    time.sleep(0.5)
                    continue
                response.raise_for_status()
                body=response.json()
                self.tokens+=int(body.get('usage',{}).get('total_tokens',0))
                content=body['choices'][0]['message'].get('content') or ''
                if content.startswith('```'):
                    content=content.strip().split('\n',1)[-1].rsplit('```',1)[0]
                result=json.loads(content)
                if not isinstance(result,dict):
                    raise ValueError('Expected JSON object')
                return result
            except (httpx.HTTPError,ValueError,KeyError,IndexError) as exc:
                # Never include provider request headers, secrets, or raw user payload in logs.
                self.provider_errors.append(type(exc).__name__)
                if attempt==1:
                    raise ProviderError('NIM request or response validation failed') from exc
        raise ProviderError('NIM unavailable')
