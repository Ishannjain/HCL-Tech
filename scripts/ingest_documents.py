import csv
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import get_settings
from app.database import connect,init_db
from app.retrieval.ingest import ingest_document
from app.schemas.source import SourceMetadata,RuleInput

def ingest_all():
    init_db();data=get_settings().data_dir
    manifest=json.loads((data/'document_manifest.json').read_text(encoding='utf-8'))
    rules=json.loads((data/'rules'/'seed_rules.json').read_text(encoding='utf-8'))
    results=[]
    with (data/'source_register.csv').open(encoding='utf-8',newline='') as stream:
        for raw in csv.DictReader(stream):
            with connect() as db:
                if db.execute("SELECT 1 FROM sources WHERE doc_id=? AND status='active'",(raw['doc_id'],)).fetchone():continue
            meta=SourceMetadata.model_validate(raw)
            name=manifest[meta.doc_id]
            results.append(ingest_document(name,(data/'documents'/name).read_bytes(),meta,
                [RuleInput.model_validate(r) for r in rules if r['source_doc_id']==meta.doc_id]))
    return results

if __name__=='__main__':print(json.dumps(ingest_all(),indent=2))
