import json
import uuid
from threading import RLock
from app.database import connect
from app.retrieval.chunking import parse_file, make_chunks
from app.retrieval.vectorstore import index_chunks, delete_ids
from app.rules.extraction import extract_explicit_rules
from app.rules.validation import validate_rule

INGEST_LOCK = RLock()

def ingest_document(filename, content, meta, provided_rules=None):
    if len(content) > 10 * 1024 * 1024:
        raise ValueError('Document exceeds 10 MB')
    chunks = make_chunks(parse_file(filename,content))
    if not chunks:
        raise ValueError('No extractable text')
    sections = {}
    for chunk in chunks:
        sections[chunk['section']] = sections.get(chunk['section'],'') + '\n' + chunk['text']
    rules = provided_rules if provided_rules is not None else (extract_explicit_rules(chunks,meta) if meta.authority_level < 5 else [])
    for rule in rules:
        validate_rule(rule,meta,sections)
    generation = uuid.uuid4().hex
    ids = [f'{meta.doc_id}:{generation}:{i}' for i in range(len(chunks))]
    with INGEST_LOCK:
        with connect() as db:
            if db.execute('SELECT 1 FROM sources WHERE doc_id=?',(meta.doc_id,)).fetchone():
                raise ValueError('doc_id already exists; use a new version ID and supersedes metadata')
            if any(db.execute('SELECT 1 FROM rule_registry WHERE rule_id=?',(r.rule_id,)).fetchone() for r in rules):
                raise ValueError('rule_id already exists')
        indexed = False
        try:
            index_chunks(ids,chunks,meta.doc_id)
            indexed = True
            with connect() as db:
                db.execute('INSERT INTO sources VALUES (?,?,?,?,?)',(meta.doc_id,json.dumps(meta.model_dump(mode='json')),
                    '\n'.join(t for _,t in parse_file(filename,content)),'active',generation))
                db.executemany('INSERT INTO chunks VALUES (?,?,?,?,?)',[(cid,meta.doc_id,c['section'],c['page'],c['text']) for cid,c in zip(ids,chunks)])
                for rule in rules:
                    raw=rule.model_dump(mode='json')
                    db.execute('INSERT INTO rule_registry VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',(
                        raw['rule_id'],raw['description'],raw['parameter'],raw['operator'],raw['value'],raw['scope_categories'].upper(),
                        raw['scope_tiers'].upper(),raw['effective_from'],raw['effective_to'] or '',raw['source_doc_id'],raw['source_section'],
                        json.dumps(raw['conditions']),raw['evidence_quote']))
        except Exception:
            if indexed:
                delete_ids(ids)
            raise
    return {'doc_id':meta.doc_id,'chunks_indexed':len(chunks),'rules_activated':len(rules),
        'status':'active','warnings':([] if rules or meta.authority_level==5 else ['No supported deterministic rules extracted; policy text only. Supply validated structured rules for unsupported rule kinds.'])}
