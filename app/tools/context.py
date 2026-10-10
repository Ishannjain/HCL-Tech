from app.rules.precedence import resolve_rule
from app.retrieval.citations import rule_citation, unique_citations

class ToolContext:
    def __init__(self,db,customer_id,as_of):
        self.db,self.customer_id,self.as_of=db,customer_id,as_of
        self.rules,self.conflicts,self.calls,self.citations=[],[],[],[]

    def rule(self,param,item,reason=None):
        rule,conflicts=resolve_rule(self.db,param,self.as_of,item['category'],item['tier'],reason)
        self.rules.append({'rule_id':rule['rule_id'],'parameter':param,'operator':rule['operator'],'value':rule['value'],'source_doc_id':rule['source_doc_id'],'source_section':rule['source_section']})
        self.conflicts.extend(conflicts)
        self.citations=unique_citations(self.citations+[rule_citation(rule)])
        return rule

    def call(self,name,input_,fn):
        import time
        start=time.perf_counter()
        output=fn()
        self.calls.append({'tool':name,'input':input_,'output':output,'ms':round((time.perf_counter()-start)*1000,2)})
        return output
