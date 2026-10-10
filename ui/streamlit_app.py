import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
import os
import re
from datetime import date
import httpx
import streamlit as st
from ui.api_client import ask_api

st.set_page_config(page_title='Retail support agent',page_icon='🛍️',layout='wide')
st.markdown('''<style>
.stMainBlockContainer {max-width: 980px; padding-top: 2rem;}
[data-testid="stChatMessage"] {border-radius: 18px; padding: 1.25rem; margin-bottom: 1rem;}
[data-testid="stMetricValue"] {font-size: 2rem;}
[data-testid="stMetricLabel"] {font-size: .9rem;}
</style>''',unsafe_allow_html=True)
st.title('Shopping support')
st.caption('Ask about your orders, returns, refunds and warranties. Synthetic hackathon demo · not a live Croma service.')

def policy_text(result):
    text=result['answer']
    # Only remove display scaffolding; policy facts stay verbatim in the response.
    for source in result.get('citations',[]):
        text=text.replace(f"{source['title']} ({source['section']}):\n",'')
    if result.get('citations') and all(s['title'].startswith('Croma') for s in result['citations']):
        text=re.sub(r'\bWe send\b','Croma sends',text)
        text=re.sub(r'\bWe (will|can|have|are)\b',lambda m:'Croma '+{'will':'will','can':'can','have':'has','are':'is'}[m.group(1)],text)
    paragraphs=[]
    seen=set()
    for passage in text.split('\n\n'):
        passage=re.sub(r"^[A-Z][A-Z0-9\s.,'’/&()\-:]*\?\s*",'',passage.strip())
        passage=re.sub(r'^(?:RETURNS|REFUND|WARRANTY)\s+','',passage)
        if not passage:continue
        for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z])',passage):
            normalized=' '.join(sentence.lower().split())
            if normalized not in seen:
                seen.add(normalized);paragraphs.append(sentence.strip())
    return '\n\n'.join(paragraphs)

def show_warranty(warranty):
    labels={'VALID':'Your recorded warranty is still active.', 'EXPIRED':'Your recorded warranty has expired.',
            'NOT_STARTED':'Your recorded warranty has not started yet.', 'NO_WARRANTY':'No warranty period is recorded for this item.'}
    st.write(labels.get(warranty.get('result'),'Warranty information needs verification.'))
    if warranty.get('expires_on'):
        st.caption('Recorded expiry: '+date.fromisoformat(warranty['expires_on']).strftime('%d %b %Y'))
    if warranty.get('message'):st.caption(warranty['message'])

def render_reply(result):
    """Present verified tool values; never ask a model to rewrite financial facts."""
    outputs={call['tool']:call.get('output') for call in result.get('tools_invoked',[])}
    refund=outputs.get('calculate_refund') or {}
    eligibility=outputs.get('check_return_eligibility') or {}
    if result['answer_type']=='calculated' and refund.get('refund_amount') is not None:
        st.markdown('Your item is **eligible for a return and refund**.')
        items=outputs.get('find_order_items') or []
        if len(items)==1:
            st.caption(f"{items[0]['name']} · Order {items[0]['order_id']} · {items[0]['sku']}")
        with st.container(border=True):
            st.metric('Estimated refund',f"₹{refund['refund_amount']:,.2f}")
            st.markdown(f"Item amount **₹{refund['gross_amount']:,.2f}**")
            fee_cols=st.columns(2)
            fee_cols[0].caption(f"Restocking fee: ₹{refund['restocking_fee']:,.2f}")
            fee_cols[1].caption(f"Return shipping: ₹{refund['reverse_shipping_fee']:,.2f}")
        if eligibility.get('window_days') is not None:
            st.write(f"You're within the {eligibility['window_days']}-day return window ({eligibility['days_since_delivery']} days since delivery).")
        if refund.get('approval_required'):
            st.info('This estimate needs approval from the support team before a refund can proceed.')
        st.caption('This is an estimate. No refund has been issued.')
        for assumption in result.get('assumptions',[]):st.info(assumption)
        # Preserve any additional warranty result in a multi-step response.
        if outputs.get('check_warranty'):show_warranty(outputs['check_warranty'])
    elif result['answer_type']=='retrieved_fact':
        st.write(policy_text(result))
    elif result['answer_type']=='calculated' and eligibility:
        if eligibility.get('result')=='ELIGIBLE':
            remedy={'REFUND':'a return and refund','REPLACEMENT':'a replacement'}.get(eligibility.get('disposition'),'a return')
            st.write(f"Your item is eligible for **{remedy}**.")
            if eligibility.get('window_days') is not None:
                st.caption(f"{eligibility['days_since_delivery']} days since delivery · {eligibility['window_days']}-day return window")
        else:st.write(eligibility.get('message',result['answer']))
        if refund.get('message'):st.write(refund['message'])
        if outputs.get('check_warranty'):show_warranty(outputs['check_warranty'])
        for assumption in result.get('assumptions',[]):st.info(assumption)
    elif result['answer_type']=='calculated' and outputs.get('check_warranty'):
        show_warranty(outputs['check_warranty'])
    elif result['answer_type']=='calculated' and outputs.get('lookup_order'):
        order=outputs['lookup_order']
        st.write(f"Your order **{order['order_id']}** is **{order['status'].lower()}**.")
    else:
        st.write(result['answer'])
    sources=result.get('citations',[])
    if sources:
        with st.expander(f'Sources & policy details ({len(sources)})'):
            for source in sources:
                provenance=source.get('provenance','')
                title=source['title']
                if provenance.startswith('https://'):st.markdown(f'[{title}]({provenance})')
                else:st.write(title)
                label=f"{source['section']} · {source['version']} · Effective {source['effective_from']}"
                if source.get('synthetic')=='Y':label+=' · Synthetic demo policy'
                st.caption(label)
    with st.expander('How this was calculated' if refund else 'Answer details'):
        st.caption(f"Answer type: {result['answer_type']} · Trace: {result['trace_id']}")
        st.json(result)
url=os.getenv('RETAIL_API_URL','http://127.0.0.1:8000')
if 'login_session' not in st.session_state:
    st.subheader('Welcome back')
    st.write('Sign in to get help with your orders and returns.')
    with st.form('customer_login',clear_on_submit=True):
        username=st.text_input('Username',placeholder='customer1 or customer2')
        password=st.text_input('Password',type='password')
        submitted=st.form_submit_button('Sign in',use_container_width=True)
    if submitted:
        try:
            response=httpx.post(url+'/auth/login',json={'username':username,'password':password},timeout=15)
            if response.status_code==401:st.error('Incorrect username or password. Please try again.')
            else:
                response.raise_for_status()
                st.session_state.login_session=response.json()
                st.session_state.messages=[]
                st.rerun()
        except httpx.HTTPError:st.error('Sign-in service is unavailable. Please try again shortly.')
    with st.expander('Demo accounts'):
        st.caption('These are fictional hackathon accounts, not real customer credentials.')
        st.markdown('**Customer 1** · `C1001`  \nUsername: `customer1`  \nPassword: `Customer1@123`')
        st.markdown('**Customer 2** · `C1002`  \nUsername: `customer2`  \nPassword: `Customer2@123`')
    st.stop()
session=st.session_state.login_session
customer=session['customer_id']
try:
    session_check=httpx.get(url+'/auth/me',headers={'Authorization':'Bearer '+session['access_token']},timeout=10)
    if session_check.status_code==401:
        st.session_state.clear();st.rerun()
    session_check.raise_for_status()
except httpx.HTTPError:
    st.error('Your account service is unavailable. Please try again shortly.');st.stop()
with st.sidebar:
    st.subheader('Your account')
    st.write(session['full_name'])
    st.caption(f"{customer} · {session['tier'].title()} member")
    if st.button('Sign out',use_container_width=True):
        try:httpx.post(url+'/auth/logout',headers={'Authorization':'Bearer '+session['access_token']},timeout=10).raise_for_status()
        except httpx.HTTPError:pass
        st.session_state.clear();st.rerun()
    as_of=st.date_input('As-of date',date(2026,10,10))
    if st.button('Check service'):
        try:st.json(httpx.get(url.rstrip('/')+'/health',timeout=10).json())
        except httpx.HTTPError:st.error('API is unavailable. Start the API server first.')
    example_order='O-100051' if customer=='C1001' else 'O-100058'
    st.caption(f'Try: How much refund for defective item {example_order} SKU-0001?')
    if st.button('Clear conversation'):st.session_state.messages=[]
if 'messages' not in st.session_state:st.session_state.messages=[]
for message in st.session_state.messages:
    with st.chat_message(message['role']):
        if message.get('result'):render_reply(message['result'])
        else:st.write(message['text'])
question=st.chat_input('Ask a policy, order, return, refund, or warranty question')
if question:
    st.session_state.messages.append({'role':'user','text':question})
    with st.chat_message('user'):st.write(question)
    with st.chat_message('assistant'):
        try:
            with st.spinner('Checking sources and authorised records…'):result=ask_api(url,question,customer,as_of,session['access_token'])
            render_reply(result)
            st.session_state.messages.append({'role':'assistant','text':result['answer'],'result':result})
        except httpx.HTTPError as exc:
            st.error(f'Request failed: {type(exc).__name__}. Check API health and configuration.')
with st.expander('Admin document ingestion'):
    st.caption('Upload a new version with its source metadata. Optional structured rules need an evidence_quote in the cited section.')
    key=st.text_input('Admin key',type='password')
    upload=st.file_uploader('Policy document',type=['txt','md','pdf','docx'])
    metadata=st.text_area('Source Register metadata JSON',height=130)
    rules=st.text_area('Optional rule list JSON',height=100)
    if st.button('Ingest document'):
        if not upload or not metadata:st.error('Document and metadata are required.')
        else:
            try:
                json.loads(metadata)
                data={'metadata':metadata}
                if rules:json.loads(rules);data['rules']=rules
                response=httpx.post(url.rstrip('/')+'/ingest',headers={'X-Admin-Key':key},files={'file':(upload.name,upload.getvalue())},data=data,timeout=180)
                response.raise_for_status();st.json(response.json())
            except (ValueError,httpx.HTTPError):st.error('Ingestion failed. Check metadata, rules, admin key, and API logs.')
