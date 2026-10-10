import argparse
import csv
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.database import connect,init_db
from scripts.validate_data import read_data,validate,FIELDS

def load_data(directory,allow_judge=True):
    data=read_data(directory)
    errors=validate(data,allow_judge)
    if errors:raise ValueError('\n'.join(errors))
    init_db()
    with connect() as db:
        for table,fields in FIELDS.items():
            for row in data[table]:
                db.execute(f"INSERT INTO {table} ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",[row[f] or None if f=='delivered_on' else row[f] for f in fields])
        facts=Path(directory)/'order_facts.csv'
        if facts.exists():
            with facts.open(encoding='utf-8-sig',newline='') as stream:
                for row in csv.DictReader(stream):
                    parsed=json.loads(row['facts'])
                    allowed={'qc_passed','brand_certified','activated','inventory_available','installed_by_authorized_brand'}
                    if not isinstance(parsed,dict) or set(parsed)-allowed or any(not isinstance(v,bool) for v in parsed.values()):
                        raise ValueError('Invalid order facts')
                    db.execute('INSERT INTO order_facts VALUES (?,?,?)',(row['order_id'],row['sku'],json.dumps(parsed)))
    return {k:len(v) for k,v in data.items()}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--dir',required=True,type=Path)
    parser.add_argument('--team-data',action='store_true')
    args=parser.parse_args()
    print(json.dumps(load_data(args.dir,not args.team_data),indent=2))
