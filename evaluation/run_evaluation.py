import argparse
import json
import os
import tempfile
from contextlib import contextmanager
from collections import Counter
from pathlib import Path
from evaluation.metrics import score,percentile,mean

ROOT=Path(__file__).resolve().parents[1]

@contextmanager
def evaluation_runtime():
    # Chroma's native Windows handles may outlive a collection. Keep the isolated
    # workspace runtime rather than failing an otherwise valid evaluation on cleanup.
    work=ROOT/'work';work.mkdir(exist_ok=True)
    directory=tempfile.mkdtemp(prefix='retail-eval-',dir=work)
    yield directory

def run(output,top_k=8,live=False,backend='keyword'):
    # Always evaluate in a separate database; never mutate the demo or judge records.
    with evaluation_runtime() as temp:
        os.environ['RUNTIME_DIR']=temp
        os.environ['MOCK_LLM']='false' if live else 'true'
        os.environ['RETRIEVAL_BACKEND']=backend
        os.environ['RETRIEVAL_TOP_K']=str(top_k)
        from app.config import get_settings
        get_settings.cache_clear()
        if live and not get_settings().nvidia_api_key:raise ValueError('Configure NVIDIA_API_KEY before live evaluation')
        from app.retrieval.vectorstore import collection
        collection.cache_clear()
        from scripts.bootstrap import bootstrap
        bootstrap()
        from app.graph.workflow import ask
        from app.schemas.request import AskRequest
        from app.database import connect
        cases=[json.loads(l) for l in (ROOT/'evaluation'/'questions.jsonl').read_text(encoding='utf-8').splitlines() if l]
        results=[]
        for case in cases:
            response=ask(AskRequest(question=case['question'],as_of_date=case['as_of_date']),case['customer_id'])
            with connect() as db:record=json.loads(db.execute('SELECT record FROM audit WHERE trace_id=?',(response['trace_id'],)).fetchone()[0])
            grade=score(case,response)
            grade['retrieval_hit']=case['expected_source'] in {s['doc_id'] for s in record['sources_retrieved']} if case.get('expected_source') else None
            results.append({'case':case,'response':response,'audit':record,'grade':grade})
        citations=[r['grade']['citation_reference_match'] for r in results if r['grade']['citation_reference_match'] is not None]
        tools=[assertion for r in results for assertion in r['grade']['tool_assertions']]
        hits=[r['grade']['retrieval_hit'] for r in results if r['grade']['retrieval_hit'] is not None]
        report={'mode':'NVIDIA NIM live' if live else 'MOCK_LLM; no real-model quality claim','model':get_settings().nvidia_model,
            'retrieval_backend':backend,'top_k':top_k,'question_count':len(cases),'tags':dict(Counter(t for c in cases for t in c['tags'])),
            'metrics':{'answer_contract_correctness':mean([r['grade']['passed'] for r in results]),'citation_expected_reference_match':mean(citations),
                'abstention_accuracy':mean([r['grade']['abstention_correct'] for r in results]),'tool_result_correctness':mean(tools),
                'retrieval_hit_rate':mean(hits),'p50_latency_ms':percentile([r['audit']['latency_ms'] for r in results],.5),
                'p95_latency_ms':percentile([r['audit']['latency_ms'] for r in results],.95),
                'llm_calls_per_question':mean([r['audit']['llm_calls'] for r in results]),'tokens_per_question':mean([r['audit']['tokens'] for r in results])},
            'method':'Independent exact expected numeric/date/tool results and expected citation IDs. Citation reference match does not measure every claim semantically; free prose and clause support still require human review.',
            'results':results}
        output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,indent=2),encoding='utf-8')
        audit_sample=ROOT/'docs'/'audit_examples.json'
        chosen=[];types=set()
        for r in results:
            if r['response']['answer_type'] not in types:
                chosen.append(r['audit']);types.add(r['response']['answer_type'])
            if len(chosen)==3:break
        audit_sample.write_text(json.dumps(chosen,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2))
        return report

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='evaluation/reports/mock_report.json')
    parser.add_argument('--top-k',type=int,default=8)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--backend',choices=['keyword','chroma'],default='keyword')
    args=parser.parse_args();run(args.output,args.top_k,args.live,args.backend)
