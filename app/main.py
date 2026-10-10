import json
import secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI,Header,HTTPException,UploadFile,File,Form,Depends
from pydantic import ValidationError
from app.config import get_settings
from app.database import connect,init_db,active_sources
from app.schemas.request import AskRequest,ReturnRequest,today
from app.schemas.response import AskResponse
from app.schemas.source import SourceMetadata,RuleInput
from app.graph.workflow import ask
from app.retrieval.ingest import ingest_document
from app.security.authorization import AccessDenied
from app.tools.context import ToolContext
from app.tools.return_tools import create_return
from app.rules.precedence import RuleMissing,RuleConflict

@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app=FastAPI(title='Retail Support Agent',version='1.0.0',lifespan=lifespan)

def require_admin(x_admin_key:str|None=Header(default=None)):
    key=get_settings().admin_api_key
    if not key or not x_admin_key or not secrets.compare_digest(key,x_admin_key):
        raise HTTPException(403,'Admin authorization required')

@app.post('/ask',response_model=AskResponse)
def ask_route(body:AskRequest,x_customer_id:str|None=Header(default=None)):
    try:return ask(body,x_customer_id)
    except Exception as exc:
        # A dependency failure is not an evidence-based not_found answer.
        raise HTTPException(503,'A support-agent dependency is unavailable. No action was taken.') from exc

@app.post('/ingest',dependencies=[Depends(require_admin)])
async def ingest_route(file:UploadFile=File(...),metadata:str=Form(...),rules:str|None=Form(default=None)):
    try:
        meta=SourceMetadata.model_validate_json(metadata)
        supplied=None if rules is None else [RuleInput.model_validate(r) for r in json.loads(rules)]
        content=await file.read(10*1024*1024+1)
        # Blocking embedding work must not run on the async event loop.
        from starlette.concurrency import run_in_threadpool
        return await run_in_threadpool(ingest_document,file.filename or 'document.txt',content,meta,supplied)
    except (ValueError,ValidationError) as exc:raise HTTPException(422,str(exc)) from exc

@app.get('/sources')
def sources_route():
    with connect() as db:return list(active_sources(db).values())

@app.get('/audit/{trace_id}')
def audit_route(trace_id:str,x_customer_id:str|None=Header(default=None),x_admin_key:str|None=Header(default=None)):
    settings=get_settings()
    admin=bool(settings.admin_api_key and x_admin_key and secrets.compare_digest(settings.admin_api_key,x_admin_key))
    with connect() as db:
        row=db.execute('SELECT * FROM audit WHERE trace_id=?',(trace_id,)).fetchone()
        if not row or (not admin and (not x_customer_id or row['customer_id']!=x_customer_id)):
            raise HTTPException(404,'Audit record unavailable')
        return json.loads(row['record'])

@app.get('/health')
def health_route():
    settings=get_settings()
    state={'api':'ready','sqlite':'unavailable','vector_store':'unavailable','llm':{},'mode':'mock' if settings.mock_llm else 'nim','retailer_mode':'synthetic hackathon dataset; not a live Croma service'}
    try:
        with connect() as db:
            db.execute('SELECT 1').fetchone()
            state['sqlite']='ready';state['sources_active']=len(active_sources(db))
    except Exception:pass
    if settings.retrieval_backend=='chroma':
        try:
            from app.retrieval.vectorstore import collection
            state['vector_store']='ready';state['chunks_indexed']=collection().count()
        except Exception:pass
    else:state['vector_store']='keyword-test-mode'
    state['llm']={'provider':'mock' if settings.mock_llm else 'nvidia-nim','configured':settings.mock_llm or bool(settings.nvidia_api_key),
                  'model':settings.nvidia_model,'connectivity':'not_probed' if not settings.mock_llm else 'mock'}
    state['ready']=state['sqlite']=='ready' and state['vector_store'] in {'ready','keyword-test-mode'} and state['llm']['configured']
    return state

@app.post('/returns')
def return_route(body:ReturnRequest,x_customer_id:str|None=Header(default=None)):
    try:
        with connect() as db:
            ctx=ToolContext(db,x_customer_id,today())
            return create_return(ctx,body.order_id,body.sku,body.reason,body.idempotency_key)
    except AccessDenied as exc:raise HTTPException(403,str(exc)) from exc
    except (ValueError,RuleMissing,RuleConflict) as exc:raise HTTPException(409,str(exc)) from exc
