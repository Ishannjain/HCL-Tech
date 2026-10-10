"""Reconcile persisted vectors from active SQLite chunks after a crash."""
from app.database import connect
from app.retrieval.vectorstore import collection,index_chunks

def recover():
    with connect() as db:
        rows=[dict(r) for r in db.execute("SELECT c.* FROM chunks c JOIN sources s USING(doc_id) WHERE s.status='active'")]
    wanted={r['chunk_id'] for r in rows}
    store=collection();existing=set(store.get(include=[])['ids'])
    orphaned=existing-wanted
    if orphaned:store.delete(ids=list(orphaned))
    missing=[r for r in rows if r['chunk_id'] not in existing]
    for doc in {r['doc_id'] for r in missing}:
        group=[r for r in missing if r['doc_id']==doc]
        index_chunks([r['chunk_id'] for r in group],group,doc)
    return {'orphaned_removed':len(orphaned),'chunks_restored':len(missing)}

if __name__=='__main__':print(recover())
