import httpx

def ask_api(url,question,customer_id,as_of):
    headers={'X-Customer-Id':customer_id} if customer_id else {}
    response=httpx.post(url.rstrip('/')+'/ask',headers=headers,json={'question':question,'as_of_date':str(as_of)},timeout=150)
    response.raise_for_status()
    return response.json()
