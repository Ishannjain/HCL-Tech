import json
import sqlite3
from contextlib import contextmanager
from app.config import get_settings

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS customers (
 customer_id TEXT PRIMARY KEY, full_name TEXT NOT NULL, tier TEXT NOT NULL CHECK(tier IN ('STANDARD','GOLD','PLATINUM')), city TEXT NOT NULL, joined_year INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS products (
 sku TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, price REAL NOT NULL CHECK(price>0), warranty_months INTEGER NOT NULL CHECK(warranty_months>=0));
CREATE TABLE IF NOT EXISTS orders (
 order_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(customer_id), order_date TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('PLACED','SHIPPED','DELIVERED','CANCELLED')), payment_method TEXT NOT NULL CHECK(payment_method IN ('UPI','CARD','COD')), delivery_note TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS order_items (
 order_id TEXT NOT NULL REFERENCES orders(order_id), sku TEXT NOT NULL REFERENCES products(sku), qty INTEGER NOT NULL CHECK(qty>=1),
 net_unit_price REAL NOT NULL CHECK(net_unit_price>0), delivered_on TEXT, PRIMARY KEY(order_id,sku));
CREATE TABLE IF NOT EXISTS returns (
 return_id TEXT PRIMARY KEY, order_id TEXT NOT NULL, sku TEXT NOT NULL, requested_on TEXT NOT NULL,
 reason TEXT NOT NULL CHECK(reason IN ('DEFECTIVE','DAMAGED','WRONG_ITEM','CHANGED_MIND')),
 status TEXT NOT NULL CHECK(status IN ('REQUESTED','PICKED_UP','REFUNDED','REJECTED')), refund_amount REAL NOT NULL DEFAULT 0,
 FOREIGN KEY(order_id,sku) REFERENCES order_items(order_id,sku));
CREATE TABLE IF NOT EXISTS sources (
 doc_id TEXT PRIMARY KEY, metadata TEXT NOT NULL, content TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'staged', generation TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chunks (
 chunk_id TEXT PRIMARY KEY, doc_id TEXT NOT NULL REFERENCES sources(doc_id), section TEXT NOT NULL, page INTEGER NOT NULL, text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rule_registry (
 rule_id TEXT PRIMARY KEY, description TEXT NOT NULL, parameter TEXT NOT NULL, operator TEXT NOT NULL, value TEXT NOT NULL,
 scope_categories TEXT NOT NULL, scope_tiers TEXT NOT NULL, effective_from TEXT NOT NULL, effective_to TEXT NOT NULL DEFAULT '',
 source_doc_id TEXT NOT NULL REFERENCES sources(doc_id), source_section TEXT NOT NULL,
 conditions TEXT NOT NULL DEFAULT '{}', evidence_quote TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS order_facts (
 order_id TEXT NOT NULL, sku TEXT NOT NULL, facts TEXT NOT NULL, PRIMARY KEY(order_id,sku), FOREIGN KEY(order_id,sku) REFERENCES order_items(order_id,sku));
CREATE TABLE IF NOT EXISTS audit (
 trace_id TEXT PRIMARY KEY, customer_id TEXT, record TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS return_operations (
 customer_id TEXT NOT NULL, idempotency_key TEXT NOT NULL, fingerprint TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(customer_id,idempotency_key));
CREATE TABLE IF NOT EXISTS approvals (
 approval_id TEXT PRIMARY KEY, return_id TEXT NOT NULL REFERENCES returns(return_id), status TEXT NOT NULL DEFAULT 'PENDING');
CREATE INDEX IF NOT EXISTS idx_orders_owner ON orders(customer_id,order_id);
CREATE INDEX IF NOT EXISTS idx_rule_parameter ON rule_registry(parameter);
'''

@contextmanager
def connect():
    settings = get_settings()
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(settings.db_path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def init_db():
    with connect() as db:
        db.executescript(SCHEMA)

def active_sources(db):
    return {r['doc_id']: json.loads(r['metadata']) for r in db.execute("SELECT * FROM sources WHERE status='active'")}
