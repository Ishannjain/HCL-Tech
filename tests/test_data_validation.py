import copy
from app.config import get_settings
from scripts.validate_data import read_data,validate

def test_converted_dataset(seeded):
    data=read_data(get_settings().data_dir/'synthetic')
    assert validate(data)==[]
    assert len(data['customers'])>=30 and len(data['products'])>=20 and len(data['orders'])>=60
    assert len({r['tier'] for r in data['customers']})>=2
    assert len({r['category'] for r in data['products']})>=5

def test_invalid_constraints(seeded):
    data=read_data(get_settings().data_dir/'synthetic')
    data['order_items'][0]['net_unit_price']='999999'
    data['order_items'][1]['qty']='0'
    data['orders'][0]['status']='BAD'
    assert len(validate(data))>=3

def test_delivery_dates_and_composite_references(seeded):
    data=read_data(get_settings().data_dir/'synthetic')
    data['order_items'][0]['delivered_on']='1900-01-01'
    data['returns'][0]['sku']='SKU-NONEXISTENT'
    assert len(validate(data))>=2

def test_judge_ids_accepted_only_by_judge_loader(seeded):
    data=read_data(get_settings().data_dir/'synthetic')
    old=data['customers'][0]['customer_id']
    data['customers'][0]['customer_id']='C9001'
    for r in data['orders']:
        if r['customer_id']==old:r['customer_id']='C9001'
    assert any('reserved' in e for e in validate(data))
    assert validate(data,True)==[]

def test_duplicate_import_rolls_back(seeded):
    from scripts.load_data import load_data
    from app.database import connect
    import sqlite3,pytest
    with pytest.raises(sqlite3.IntegrityError):load_data(get_settings().data_dir/'synthetic')
    with connect() as db:assert db.execute('SELECT COUNT(*) FROM customers').fetchone()[0]==30
