"""Refresh only developer seed documents after a source-layout migration.

This never replaces customer data or judge documents. Normal live ingestion
uses a new document ID; this command is for local build-time seed maintenance.
"""
import csv
import json
import uuid
from app.config import get_settings
from app.database import connect
from app.schemas.source import SourceMetadata,RuleInput
from app.retrieval.chunking import make_chunks,parse_file
from app.retrieval.vectorstore import index_chunks,delete_ids
from app.rules.validation import validate_rule

def sync():
    data=get_settings().data_dir
    manifest=json.loads((data/'document_manifest.json').read_text())
    raw_rules=json.loads((data/'rules'/'seed_rules.json').read_text())
    staged=[];old_ids=[]
    try:
        with (data/'source_register.csv').open(encoding='utf-8',newline='') as stream:
            for row in csv.DictReader(stream):
                meta=SourceMetadata.model_validate(row);filename=manifest[meta.doc_id]
                content=(data/'documents'/filename).read_bytes();pages=parse_file(filename,content);chunks=make_chunks(pages)
                sections={}
                for c in chunks:sections[c['section']]=sections.get(c['section'],'')+'\n'+c['text']
                rules=[RuleInput.model_validate(r) for r in raw_rules if r['source_doc_id']==meta.doc_id]
                for r in rules:validate_rule(r,meta,sections)
                generation=uuid.uuid4().hex;ids=[f'{meta.doc_id}:{generation}:{i}' for i in range(len(chunks))]
                index_chunks(ids,chunks,meta.doc_id)
                staged.append((meta,pages,chunks,rules,generation,ids))
        with connect() as db:
            for meta,pages,chunks,rules,generation,ids in staged:
                if not db.execute('SELECT 1 FROM sources WHERE doc_id=?',(meta.doc_id,)).fetchone():raise ValueError('Bootstrap missing seed before sync')
                old_ids.extend(r['chunk_id'] for r in db.execute('SELECT chunk_id FROM chunks WHERE doc_id=?',(meta.doc_id,)))
                db.execute('DELETE FROM rule_registry WHERE source_doc_id=?',(meta.doc_id,))
                db.execute('DELETE FROM chunks WHERE doc_id=?',(meta.doc_id,))
                db.execute('UPDATE sources SET metadata=?,content=?,status=?,generation=? WHERE doc_id=?',(json.dumps(meta.model_dump(mode='json')),'\n'.join(t for _,t in pages),'active',generation,meta.doc_id))
                db.executemany('INSERT INTO chunks VALUES (?,?,?,?,?)',[(cid,meta.doc_id,c['section'],c['page'],c['text']) for cid,c in zip(ids,chunks)])
                for r in rules:
                    raw=r.model_dump(mode='json')
                    db.execute('INSERT INTO rule_registry VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',(r.rule_id,r.description,r.parameter,r.operator,r.value,r.scope_categories,r.scope_tiers,
                        str(r.effective_from),str(r.effective_to) if r.effective_to else '',r.source_doc_id,r.source_section,json.dumps(r.conditions),r.evidence_quote))
    except Exception:
        for *_,ids in staged:delete_ids(ids)
        raise
    delete_ids(old_ids)
    return {'seed_sources_updated':len(staged)}

if __name__=='__main__':print(sync())
