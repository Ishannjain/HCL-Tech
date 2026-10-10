import json
from pathlib import Path
from evaluation.run_evaluation import run

if __name__=='__main__':
    reports=[run(f'evaluation/reports/top_k_{k}.json',k,False,'keyword') for k in (2,8)]
    result=[{'top_k':r['top_k'],'metrics':r['metrics'],'mode':r['mode']} for r in reports]
    Path('evaluation/reports/comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
