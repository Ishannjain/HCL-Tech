import re
from app.database import active_sources
from app.config import get_settings
from app.rules.precedence import applicable
from app.retrieval.vectorstore import search_vector

def words(text):
    text=re.sub(r'send\s+back','return',text.lower())
    text=re.sub(r'guarantee','warranty',text)
    text=re.sub(r'\breturn(?:ed|s|ing)?\b','return',text)
    return set(re.findall(r'[a-z]{3,}',text)) - {'the','and','for','can','how','what','does','have','with','from','this','that','are','will','get','item','product','policy','you','your','our','they','their','buy','accept','deliver','raise','tell','please','steps','procedure','available','about','should','prepare'}

def retrieve(db,question,as_of,category=None,tier=None):
    settings=get_settings()
    sources=active_sources(db)
    allowed={doc:meta for doc,meta in sources.items() if applicable(meta,as_of,category,tier)}
    if not allowed:
        return []
    rows=[dict(r) for r in db.execute('SELECT * FROM chunks') if r['doc_id'] in allowed]
    qwords=words(question)
    lexical={r['chunk_id']:len(qwords & words(r['text']))/max(1,len(qwords)) for r in rows}
    scores=dict(lexical)
    if settings.retrieval_backend=='chroma':
        for result in search_vector(question,list(allowed),settings.retrieval_top_k*2):
            scores[result['chunk_id']]=scores.get(result['chunk_id'],0)+max(0,result['score'])*0.35
    ranked=sorted(rows,key=lambda r:scores.get(r['chunk_id'],0),reverse=True)
    output=[]
    for row in ranked[:settings.retrieval_top_k]:
        if lexical[row['chunk_id']]<=0:
            continue
        row.update(score=round(scores[row['chunk_id']],4),source=allowed[row['doc_id']])
        output.append(row)
    return output
