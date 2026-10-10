import math

def percentile(values,p):
    if not values:return None
    seq=sorted(values);index=(len(seq)-1)*p
    low=math.floor(index);high=math.ceil(index)
    return round(seq[low]+(seq[high]-seq[low])*(index-low),2)

def mean(values):
    return round(sum(values)/len(values),4) if values else None

def score(case,response):
    reasons=[]
    if response['answer_type']!=case['expected_answer_type']:reasons.append('answer_type mismatch')
    expected_source=case.get('expected_source')
    cited={c['doc_id'] for c in response['citations']}
    citation_ok=expected_source in cited if expected_source else None
    if expected_source and not citation_ok:reasons.append('expected source not cited')
    outputs={t['tool']:t['output'] for t in response['tools_invoked']}
    tool_results=[]
    for field,expected in case.get('expected_tool_values',{}).items():
        tool,key=field.split('.',1)
        actual=outputs.get(tool,{}).get(key)
        passed=actual==expected
        tool_results.append(passed)
        if not passed:reasons.append(f'{field}: expected {expected!r}, received {actual!r}')
    if case['expected_answer_type']=='not_found' and response['answer']!='I could not find this information in the authorised sources.':
        reasons.append('not_found message mismatch')
    return {'passed':not reasons,'reasons':reasons,'citation_reference_match':citation_ok,'tool_assertions':tool_results,
        'abstention_correct':(response['answer_type']=='not_found')==(case['expected_answer_type']=='not_found')}
