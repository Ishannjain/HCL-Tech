import csv
import json
import re
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STAMP='2026-10-10'
SOURCE_FIELDS=['doc_id','title','issuer','authority_level','doc_type','version','effective_from','effective_to','supersedes','scope_categories','scope_tiers','provenance','retrieved_on','synthetic']

def prepare_sources():
    docs=ROOT/'data'/'documents'; archive=ROOT/'data'/'original_documents'; archive.mkdir(exist_ok=True)
    paths=[('CROMA-RETURN-SNAPSHOT','croma_cancellation_returns.txt','Croma Cancellation and Returns','https://www.croma.com/cancellation-and-return',1,'Croma Replacement Policy'),
           ('CROMA-FAQ-SNAPSHOT','croma_faq.txt','Croma FAQs','https://www.croma.com/faq',4,'Frequently asked questions'),
           ('CROMA-TERMS-SNAPSHOT','croma_terms_of_use.txt','Croma Terms of Use','https://www.croma.com/terms-of-use',1,'Terms and conditions')]
    register=[];rules=[]
    for doc_id,name,title,url,authority,section in paths:
        original=archive/name
        if not original.exists():shutil.copy2(docs/name,original)
        raw=original.read_text(encoding='utf-8')
        if name=='croma_cancellation_returns.txt':
            offset=raw.find('Croma Replacement Policy');raw=raw[offset:]
        # Whitespace cleaning only; original snapshots are retained in full.
        body=re.sub(r'[ \t\xa0]+',' ',raw)
        document=f'# {section}\n{body}'
        if doc_id=='CROMA-RETURN-SNAPSHOT':
            window_start=body.index('RETURN/REPLACEMENT APPLICABLE WINDOW')
            category_match=re.search(r'CATEGORY\s*[–-]\s*RETURN POLICY',body)
            if not category_match:raise ValueError('Missing category policy heading')
            document=(f'# {section}\n'+body[:window_start]+'\n# Return replacement applicable window\n'
                +body[window_start:category_match.start()]+'\n# Category return policy\n'+body[category_match.start():])
        (docs/name).write_text(document,encoding='utf-8')
        register.append(dict(doc_id=doc_id,title=title,issuer='Croma / Infiniti Retail Limited',authority_level=authority,
            doc_type='faq' if authority==4 else 'regulation',version='snapshot-2026-10-10',effective_from=STAMP,effective_to='',supersedes='',
            scope_categories='ALL',scope_tiers='ALL',provenance=url,retrieved_on=STAMP,synthetic='N'))
        if doc_id=='CROMA-RETURN-SNAPSHOT':
            flat=re.sub(r'\s+',' ',body)
            clauses=[
                ('QC','requires_quality_check','=','true',r'All replacements and returns are subject to verification through Quality checks\.'),
                ('BRAND','requires_brand_certificate','=','true',r'Replacement is eligible only in cases of hardware related issues as certified by the brand in its technical report\.'),
                ('REPLACE','replacement_first','=','true',r'Croma offers a replacement-only policy, subject to meeting the specified replacement criteria as per brand warranty terms\.'),
                ('REMORSE','change_of_mind_allowed','=','false',r"Buyer's Remorse:.*?not eligible for replacement or return\."),
                ('DAMAGE','damage_report_hours','<=','48',r'In cases when the product delivered is damaged, a replacement request should be raised within 48 hours of order delivery\.'),
            ]
            for label,param,operator,value,pattern in clauses:
                match=re.search(pattern,flat)
                if not match:raise ValueError(f'Source clause not found for {param}')
                rule=dict(rule_id=f'CROMA-{label}',description=match.group(),parameter=param,operator=operator,value=value,
                    scope_categories='MOBILE' if param=='damage_report_hours' else 'ALL',scope_tiers='ALL',effective_from=STAMP,effective_to='',
                    source_doc_id=doc_id,source_section='Category return policy' if param in {'requires_brand_certificate','damage_report_hours'} else section,conditions={},evidence_quote=match.group())
                rules.append(rule)
            for category,label in [('LAPTOP','Laptop'),('MOBILE','Mobile Phones'),('AUDIO','Bluetooth Speaker'),('TELEVISION',r'Television \(LED\)'),('APPLIANCE','Refrigerators')]:
                match=re.search(label+r'\s+7 days',flat)
                if not match:raise ValueError(f'Missing window source for {category}')
                rules.append(dict(rule_id=f'CROMA-WINDOW-{category}',description=match.group(),parameter='return_window_days',operator='<=',value='7',
                    scope_categories=category,scope_tiers='ALL',effective_from=STAMP,effective_to='',source_doc_id=doc_id,
                    source_section='Return replacement applicable window',conditions={},evidence_quote=match.group()))
    synthetic_docs=[
        ('DEMO-OPS','demo_operations.md','Synthetic hackathon operational policy',1,'regulation','',
         '# Fee calculation\nFor this synthetic hackathon dataset only, restocking fee is 10% of net item price times quantity. Reverse shipping fee is INR 60 per return request. Round each monetary amount to two decimal places using ROUND_HALF_UP.\n'
         '# Approval\nFor this synthetic hackathon dataset only, automatic refund approval limit is INR 10000 inclusive. An estimate above the limit requires human approval. No tool issues money.\n'
         '# Warranty\nFor synthetic products, warranty starts on delivery and lasts the product record warranty_months in calendar months, inclusive of the calendar expiry date. Brand installation and exclusions still require verification.\n'
         '# Nonreturnable category\nFor this synthetic dataset only, AUDIO is a non-returnable category for all return reasons.\n'),
        ('DEMO-CIRCULAR','demo_circular.md','Synthetic AUDIO amendment',2,'circular','CROMA-RETURN-SNAPSHOT#Return replacement applicable window',
         '# Audio return window\nFor this synthetic hackathon dataset only, the AUDIO return window is 5 days. This clause supersedes the return-window clause of CROMA-RETURN-SNAPSHOT for AUDIO only.\n'),
        ('DEMO-FAQ','demo_faq.md','Synthetic outdated FAQ',4,'faq','',
         '# Return FAQ\nFor this synthetic hackathon scenario, the AUDIO return window is 15 days. This FAQ cannot override an authoritative policy or circular.\n'),
    ]
    for doc_id,name,title,authority,kind,supersedes,content in synthetic_docs:
        (docs/name).write_text(content,encoding='utf-8')
        register.append(dict(doc_id=doc_id,title=title,issuer='Hackathon test fixtures (not Croma)',authority_level=authority,doc_type=kind,
            version='1.0-demo',effective_from=STAMP,effective_to='',supersedes=supersedes,
            scope_categories='AUDIO' if doc_id!='DEMO-OPS' else 'ALL',scope_tiers='ALL',provenance=f'Synthetic local fixture: {name}',retrieved_on=STAMP,synthetic='Y'))
    def synthetic_rule(doc_id,param,value,section,quote,categories='ALL',operator='='):
        rules.append(dict(rule_id=f'{doc_id}-{param}',description=quote,parameter=param,operator=operator,value=value,
            scope_categories=categories,scope_tiers='ALL',effective_from=STAMP,effective_to='',source_doc_id=doc_id,
            source_section=section,conditions={},evidence_quote=quote))
    synthetic_rule('DEMO-OPS','restocking_fee_pct','10','Fee calculation','restocking fee is 10% of net item price times quantity.')
    synthetic_rule('DEMO-OPS','reverse_shipping_fee','60','Fee calculation','Reverse shipping fee is INR 60 per return request.')
    synthetic_rule('DEMO-OPS','auto_refund_limit','10000','Approval','automatic refund approval limit is INR 10000 inclusive.','ALL','<=')
    synthetic_rule('DEMO-OPS','warranty_start','delivery','Warranty','warranty starts on delivery')
    synthetic_rule('DEMO-OPS','non_returnable','true','Nonreturnable category','AUDIO is a non-returnable category for all return reasons.','AUDIO')
    synthetic_rule('DEMO-CIRCULAR','return_window_days','5','Audio return window','the AUDIO return window is 5 days.','AUDIO','<=')
    synthetic_rule('DEMO-FAQ','return_window_days','15','Return FAQ','the AUDIO return window is 15 days.','AUDIO','<=')
    with (ROOT/'data'/'source_register.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=SOURCE_FIELDS);writer.writeheader();writer.writerows(register)
    (ROOT/'data'/'rules'/'seed_rules.json').write_text(json.dumps(rules,indent=2),encoding='utf-8')
    (ROOT/'data'/'document_manifest.json').write_text(json.dumps({row['doc_id']:name for row,name in zip(register,[p[1] for p in paths]+[p[1] for p in synthetic_docs])},indent=2),encoding='utf-8')
    print(f'Prepared {len(register)} sources and {len(rules)} evidenced rules.')

if __name__=='__main__':prepare_sources()
