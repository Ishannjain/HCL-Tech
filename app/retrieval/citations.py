def citation(meta, section, page=1):
    return {'doc_id':meta['doc_id'],'title':meta['title'],'section':section,'page':page,
            'version':meta['version'],'effective_from':meta['effective_from'],'synthetic':meta['synthetic'],
            'provenance':meta['provenance']}

def rule_citation(rule):
    return citation(rule['source'],rule['source_section'])

def unique_citations(items):
    result, seen = [], set()
    for item in items:
        key = (item['doc_id'],item['section'],item.get('page'))
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
