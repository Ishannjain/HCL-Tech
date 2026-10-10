import json
import re
from datetime import date,timedelta
from app.config import get_settings
from app.database import connect,active_sources
from app.graph.routing import route,Plan
from app.llm.nim_client import NimClient,ProviderError
from app.llm.prompts import PLAN_PROMPT,EXTRACT_PROMPT
from app.retrieval.retriever import retrieve,words
from app.retrieval.citations import citation,rule_citation,unique_citations
from app.rules.precedence import RuleMissing,RuleConflict,resolve_rule
from app.security.authorization import AccessDenied
from app.tools.context import ToolContext
from app.tools.order_tools import lookup_order,find_items
from app.tools.return_tools import check_return_eligibility
from app.tools.refund_tools import calculate_refund
from app.tools.warranty_tools import check_warranty

NOT_FOUND='I could not find this information in the authorised sources.'

def plan_node(state):
    question=state['request'].question
    plan=route(question);client=NimClient();errors=[]
    if not get_settings().mock_llm:
        try:
            suggested=Plan.model_validate(client.json_completion(PLAN_PROMPT,question))
            # Models cannot invent entity identifiers or turn a general policy query into personal access.
            if suggested.order_id and suggested.order_id.casefold() not in question.casefold():raise ValueError('Invented order ID')
            if suggested.sku and suggested.sku.casefold() not in question.casefold():raise ValueError('Invented SKU')
            if plan.intent!='policy':
                suggested.order_id=plan.order_id or suggested.order_id
                suggested.sku=plan.sku or suggested.sku
                suggested.reason=plan.reason or suggested.reason
                plan=suggested
        except (ProviderError,ValueError) as exc:
            errors.append(type(exc).__name__)
    return {'plan':plan,'client':client,'errors':errors}

def category_from_question(db,question):
    aliases={'headphones':'AUDIO','speaker':'AUDIO','laptop':'LAPTOP','mobile':'MOBILE','phone':'MOBILE','television':'TELEVISION','tv':'TELEVISION','appliance':'APPLIANCE','audio':'AUDIO'}
    for word,cat in aliases.items():
        if re.search(r'\b'+re.escape(word)+r's?\b',question.lower()):return cat
    for row in db.execute('SELECT DISTINCT category FROM products'):
        if row['category'].casefold() in question.casefold():return row['category']
    return None

def retrieve_node(state):
    req=state['request']
    with connect() as db:
        category=category_from_question(db,req.question)
        tier='STANDARD'
        if state.get('customer_id'):
            customer=db.execute('SELECT tier FROM customers WHERE customer_id=?',(state['customer_id'],)).fetchone()
            if customer:tier=customer['tier']
        intent=state['plan'].intent
        hints={'refund':'restocking fee reverse shipping refund approval',
               'return':'return replacement window quality check defective',
               'warranty':'warranty starts delivery calendar months',
               'multistep':'return window warranty brand claim service'}
        query=req.question+' '+hints.get(intent,'')
        if intent=='policy' and re.search(r'prepare.*return|return.*prepar',req.question,re.I):
            query+=' original packaging invoice accessories condition personal information'
        chunks=retrieve(db,query,req.as_of_date,category,tier)
    return {'chunks':chunks}

def execute_node(state):
    req,plan=state['request'],state['plan']
    identity=state.get('customer_id')
    result={'answer_type':'not_found','answer':NOT_FOUND,'citations':[],'applied_rules':[],'tools_invoked':[],'conflicts_detected':[],'assumptions':[],'explanation':''}
    q=req.question.lower()
    if re.search(r'\b(?:another|other) customer|someone else|\bC\d{4}\b',req.question,re.I):
        mentioned=re.findall(r'\bC\d{4}\b',req.question,re.I)
        if any(cid.upper()!=identity for cid in mentioned) or re.search(r'another customer|other customer|someone else',q):
            result.update(answer_type='refused',answer='Requests for another customer’s data are not allowed.')
            return {'result':result}
    try:
        with connect() as db:
            if plan.intent=='policy':
                category=category_from_question(db,req.question)
                tier='STANDARD'
                if identity:
                    customer=db.execute('SELECT tier FROM customers WHERE customer_id=?',(identity,)).fetchone()
                    if customer:tier=customer['tier']
                if re.search(r'return|replacement|send back',q) and re.search(r'window|days|long|deadline',q):
                    if not category:
                        result.update(answer_type='clarification_needed',answer='Which product category is this question about?')
                        return {'result':result}
                    rule,conflicts=resolve_rule(db,'return_window_days',req.as_of_date,category,tier)
                    result.update(answer_type='retrieved_fact',answer=f"The applicable {category} return/replacement window is {rule['value']} days. This window alone does not guarantee a cash refund; the documented reason and verification conditions still apply.",
                        citations=[rule_citation(rule)],applied_rules=[{'rule_id':rule['rule_id'],'parameter':rule['parameter'],'value':rule['value'],'source_doc_id':rule['source_doc_id']}],conflicts_detected=conflicts,
                        explanation='Policy precedence: applicability, explicit supersession, authority, then effective-date recency.')
                    upcoming=[]
                    for raw in db.execute('SELECT * FROM rule_registry WHERE parameter=?',('return_window_days',)):
                        r=dict(raw);m=active_sources(db).get(r['source_doc_id'])
                        from app.rules.precedence import covers
                        if m and m['authority_level']<5 and r['effective_from']>str(req.as_of_date) and covers(r['scope_categories'],category) and covers(r['scope_tiers'],tier):
                            upcoming.append((r,m))
                    for r,m in upcoming:
                        result['answer']+=f" Upcoming: {m['title']} states {r['value']} days from {r['effective_from']}; it is not applied to this request."
                        result['citations'].append(citation(m,r['source_section']))
                    return {'result':result}
                return {'result':policy_quotes(state,result)}
            if not identity:raise AccessDenied('Sign in through X-Customer-Id for personal questions.')
            ctx=ToolContext(db,identity,req.as_of_date)
            if plan.intent=='order':
                if not plan.order_id:
                    result.update(answer_type='clarification_needed',answer='Which order ID should I look up?')
                else:
                    order=ctx.call('lookup_order',{'order_id':plan.order_id},lambda:lookup_order(db,identity,plan.order_id))
                    result.update(answer_type='calculated',answer=f"Order {order['order_id']} has status {order['status']}.",explanation='Looked up from the authenticated customer’s order records.')
            else:
                items=ctx.call('find_order_items',{'order_id':plan.order_id,'sku':plan.sku},lambda:find_items(db,identity,plan.order_id,plan.sku))
                if not plan.sku and not plan.order_id:
                    category=category_from_question(db,req.question)
                    if category:items=[i for i in items if i['category']==category]
                if len(items)!=1:
                    result.update(answer_type='clarification_needed',answer='Specify the order ID and SKU for the item. '+('Your matching items: '+', '.join(f"{i['order_id']} / {i['sku']}" for i in items[:8]) if items else 'No matching item is available in your account.'))
                else:
                    item=items[0]
                    scenario_date=req.as_of_date
                    whatif=bool(re.search(r'what if|if i were|if i was|hypothetical',q))
                    hypothetical_day=re.search(r'(?:after|at)\s+(\d+)\s+days?',q)
                    hypothetical_tier=re.search(r'\b(gold|platinum|standard)\b',q)
                    if whatif and hypothetical_day and item['delivered_on']:
                        ctx.as_of=date.fromisoformat(item['delivered_on'])+timedelta(days=int(hypothetical_day.group(1)))
                        result['assumptions'].append(f'Hypothetical evaluation date {ctx.as_of}; no state changes.')
                    if whatif and hypothetical_tier:
                        item=dict(item,tier=hypothetical_tier.group(1).upper())
                        result['assumptions'].append(f"Hypothetical tier {item['tier']}; actual account is unchanged.")
                    inputs={'order_id':item['order_id'],'sku':item['sku']}
                    if plan.intent=='warranty':
                        warranty=ctx.call('check_warranty',inputs,lambda:check_warranty(ctx,item))
                        result.update(answer_type='calculated',answer=f"Recorded warranty status: {warranty['result']}. "+warranty.get('message',''),explanation=json.dumps(warranty))
                    else:
                        eligibility=ctx.call('check_return_eligibility',dict(inputs,reason=plan.reason),lambda:check_return_eligibility(ctx,item,plan.reason))
                        if eligibility['result']=='CLARIFICATION_NEEDED':
                            result.update(answer_type='clarification_needed',answer=eligibility['message'])
                        else:
                            result.update(answer_type='calculated',answer=eligibility.get('message',f"Return eligibility: {eligibility['result']}; remedy: {eligibility.get('disposition','none')}."),explanation=json.dumps(eligibility))
                            if plan.intent in {'refund','multistep'} and eligibility['result']=='ELIGIBLE':
                                refund=ctx.call('calculate_refund',dict(inputs,reason=plan.reason),lambda:calculate_refund(ctx,item,plan.reason,eligibility))
                                if refund.get('refund_amount') is not None:
                                    result['answer']+=f" Estimated refund: INR {refund['refund_amount']:.2f} = {refund['gross_amount']:.2f} - {refund['restocking_fee']:.2f} - {refund['reverse_shipping_fee']:.2f}."
                                    if refund['approval_required']:result['answer']+=' Human approval is required.'
                                    result['answer']+=' No money has been issued.'
                                else:result['answer']+=' '+refund['message']
                            if plan.intent=='multistep' and eligibility['result']!='ELIGIBLE':
                                warranty=ctx.call('check_warranty',inputs,lambda:check_warranty(ctx,item))
                                result['answer']+=f" Recorded warranty status: {warranty['result']}. "
                                result['answer']+=warranty.get('message','')
                                steps=[c for c in state.get('chunks',[]) if 'service centre' in c['text'].lower() or 'service center' in c['text'].lower()]
                                if steps:
                                    c=steps[0]
                                    line=next((l.strip() for l in re.split(r'(?<=[.!?])\s+',c['text']) if ('service centre' in l.lower() or 'service center' in l.lower()) and len(l)<600),'')
                                    if line:
                                        result['answer']+=' Documented next step: '+line
                                        ctx.citations.append(citation(c['source'],c['section'],c['page']))
                    ctx.as_of=scenario_date
            result.update(citations=unique_citations(ctx.citations),applied_rules=ctx.rules,tools_invoked=ctx.calls,conflicts_detected=ctx.conflicts)
    except AccessDenied as exc:
        result.update(answer_type='refused',answer=str(exc),citations=[],tools_invoked=[],applied_rules=[])
    except RuleConflict as exc:
        result.update(answer_type='conflict_flagged',answer=f'Authorised sources conflict for {exc.parameter}. Contact support; no decision or action was made.',
            citations=unique_citations([rule_citation(c) for c in exc.candidates]),conflicts_detected=[{'parameter':exc.parameter,'winner':None,'resolution':['Unresolved after Annex A'],'candidates':[c['rule_id'] for c in exc.candidates]}])
        if 'ctx' in locals():result['tools_invoked']=ctx.calls;result['applied_rules']=ctx.rules
    except RuleMissing as exc:
        result.update(answer_type='not_found',answer=NOT_FOUND,explanation=str(exc))
        if 'ctx' in locals():result.update(tools_invoked=ctx.calls,applied_rules=ctx.rules,citations=unique_citations(ctx.citations))
    return {'result':result}

def policy_quotes(state,result):
    chunks=[c for c in state.get('chunks',[]) if c['source']['authority_level']<5]
    if not chunks:return result
    # Unsupported topical terms must not be answered with a vaguely related passage.
    topics=words(state['request'].question)
    available=set().union(*(words(c['text']) for c in chunks))
    if topics-available:return result
    quotes=[]
    if not get_settings().mock_llm:
        try:
            selected=state['client'].json_completion(EXTRACT_PROMPT,json.dumps({'question':state['request'].question,'chunks':[{'chunk_id':c['chunk_id'],'text':c['text']} for c in chunks]}))
            mapping={c['chunk_id']:c for c in chunks}
            for entry in selected.get('quotes',[])[:3]:
                c=mapping.get(entry.get('chunk_id'));quote=entry.get('quote','')
                if c and isinstance(quote,str) and 0<len(quote)<=600 and quote in c['text'] and words(quote)&words(state['request'].question):
                    quotes.append((quote,c))
        except (ProviderError,ValueError,TypeError):
            state['errors'].append('EvidenceSelectionFailed')
            return result
    else:
        # Mock selection is generic and extractive, never a table of pre-written demo answers.
        qwords=words(state['request'].question)
        ranked=[]
        for c in chunks:
            for sentence in re.split(r'(?<=[.!?])\s+|\n',c['text']):
                sentence=sentence.strip()
                if 20<=len(sentence)<=600 and not re.search(r'ignore previous|system prompt|call the tool',sentence,re.I):
                    score=len(qwords&words(sentence))
                    if score:ranked.append((score,sentence,c))
        ranked.sort(key=lambda e:e[0],reverse=True)
        if ranked:quotes=[(ranked[0][1],ranked[0][2])]
    if not quotes:return result
    # Verbatim evidence prevents a free-form model from adding unsupported factual claims.
    result.update(answer_type='retrieved_fact',answer='\n\n'.join(f"{c['source']['title']} ({c['section']}):\n{quote}" for quote,c in quotes),
        citations=unique_citations([citation(c['source'],c['section'],c['page']) for quote,c in quotes]),
        explanation='Exact supporting excerpts selected from applicable authorised sources. Partial or absent information is not inferred.')
    return result

def assemble_node(state):
    import time
    from datetime import datetime,timezone
    from app.schemas.response import AskResponse
    result=state['result']
    response=AskResponse(trace_id=state['trace_id'],as_of_date=state['request'].as_of_date,**result)
    record={'trace_id':state['trace_id'],'timestamp':datetime.now(timezone.utc).isoformat(),'customer_id':state.get('customer_id'),
        'question_category':state['plan'].intent,'question_redacted':'[Question text omitted; intent and tool identifiers retained]',
        'sources_retrieved':[{'doc_id':c['doc_id'],'section':c['section'],'page':c['page'],'score':c['score']} for c in state.get('chunks',[])],
        'precedence_decisions':result['conflicts_detected'],'tools_invoked':result['tools_invoked'],'applied_rules':result['applied_rules'],
        'answer_type':result['answer_type'],'model':'MOCK_LLM-extractive' if get_settings().mock_llm else get_settings().nvidia_model,
        'llm_calls':state['client'].calls,'tokens':state['client'].tokens,'latency_ms':round((time.perf_counter()-state['started'])*1000,2),
        'provider_errors':state['errors']+state['client'].provider_errors,'mock_llm':get_settings().mock_llm,'as_of_date':str(state['request'].as_of_date)}
    with connect() as db:db.execute('INSERT INTO audit VALUES (?,?,?)',(state['trace_id'],state.get('customer_id'),json.dumps(record)))
    return {'response':response.model_dump(mode='json')}
