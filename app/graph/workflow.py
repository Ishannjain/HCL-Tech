import time
import uuid
from functools import lru_cache
from langgraph.graph import StateGraph,START,END
from app.graph.state import AgentState
from app.graph.nodes import plan_node,retrieve_node,execute_node,assemble_node

@lru_cache
def workflow():
    graph=StateGraph(AgentState)
    for name,node in [('plan',plan_node),('retrieve',retrieve_node),('execute',execute_node),('assemble',assemble_node)]:graph.add_node(name,node)
    graph.add_edge(START,'plan');graph.add_edge('plan','retrieve');graph.add_edge('retrieve','execute');graph.add_edge('execute','assemble');graph.add_edge('assemble',END)
    return graph.compile()

def ask(request,customer_id):
    return workflow().invoke({'request':request,'customer_id':customer_id,'trace_id':uuid.uuid4().hex,'started':time.perf_counter()},config={'recursion_limit':10})['response']
