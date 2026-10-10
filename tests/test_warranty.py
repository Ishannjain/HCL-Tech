from datetime import date
from app.tools.warranty_tools import add_months

def test_calendar_month_ends():
    assert add_months(date(2026,1,31),1)==date(2026,2,28)
    assert add_months(date(2024,1,31),1)==date(2024,2,29)
    assert add_months(date(2024,2,29),12)==date(2025,2,28)

def test_exact_expiry_boundary(client):
    from tests.conftest import ask
    valid=ask(client,'Is my item O-100055 SKU-0001 under warranty?',as_of='2026-10-09')
    # Snapshot metadata does not authorize a historical warranty rule before 10 Oct.
    assert valid['answer_type']=='not_found'
    from app.database import connect
    from app.tools.context import ToolContext
    from app.tools.order_tools import find_items
    from app.tools.warranty_tools import check_warranty
    with connect() as db:
        item=find_items(db,'C1001','O-100051','SKU-0001')[0]
        ctx=ToolContext(db,'C1001',date(2027,4,3))
        assert check_warranty(ctx,item)['result']=='VALID'
        ctx.as_of=date(2027,4,4)
        assert check_warranty(ctx,item)['result']=='EXPIRED'
