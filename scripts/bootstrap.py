import json
from app.config import get_settings
from app.database import connect,init_db
from scripts.load_data import load_data
from scripts.ingest_documents import ingest_all

def bootstrap():
    init_db()
    with connect() as db:
        count=db.execute('SELECT COUNT(*) FROM customers').fetchone()[0]
    loaded=load_data(get_settings().data_dir/'synthetic',False) if count==0 else {'status':'existing data preserved'}
    return {'data':loaded,'sources':ingest_all()}

if __name__=='__main__':print(json.dumps(bootstrap(),indent=2))
