import json
from datetime import date
from app.database import active_sources

class RuleMissing(Exception):
    pass

class RuleConflict(Exception):
    def __init__(self, parameter, candidates):
        self.parameter, self.candidates = parameter, candidates
        super().__init__(f'Unresolved conflict for {parameter}')

def covers(scope, value):
    values = {v.strip().upper() for v in scope.split(';')}
    return 'ALL' in values or (value is not None and value.upper() in values)

def applicable(meta, as_of, category=None, tier=None):
    stamp = str(as_of)
    return (meta['effective_from'] <= stamp and (not meta.get('effective_to') or meta['effective_to'] >= stamp)
            and covers(meta['scope_categories'], category) and covers(meta['scope_tiers'], tier))

def choose(candidates, parameter):
    """Annex A order; candidates must already be applicable."""
    trusted = [c for c in candidates if c['source']['authority_level'] < 5]
    if not trusted:
        raise RuleMissing(f'No authorized applicable rule for {parameter}')
    superseded = set()
    decisions = []
    for candidate in trusted:
        meta = candidate['source']
        if meta['authority_level'] not in (1, 2):
            continue
        for target in filter(None, (t.strip() for t in meta.get('supersedes','').split(';'))):
            doc, _, clause = target.partition('#')
            for other in trusted:
                if other['source']['doc_id'] != meta['doc_id'] and other['source']['doc_id'] == doc and (not clause or other['source_section'] == clause):
                    superseded.add(other['rule_id'])
                    decisions.append(f"{meta['doc_id']}#{candidate['source_section']} supersedes {target} (step 2)")
    survivors = [c for c in trusted if c['rule_id'] not in superseded]
    if not survivors:
        raise RuleConflict(parameter, trusted)
    authority = min(c['source']['authority_level'] for c in survivors)
    authoritative = [c for c in survivors if c['source']['authority_level'] == authority]
    latest = max(c['effective_from'] for c in authoritative)
    winners = [c for c in authoritative if c['effective_from'] == latest]
    signatures = {(c['operator'], c['value']) for c in winners}
    if len(signatures) > 1:
        raise RuleConflict(parameter, winners)
    winner = sorted(winners, key=lambda c:c['rule_id'])[0]
    if len(trusted) > len(authoritative):
        decisions.append(f'Authority level {authority} prevails over lower-authority content (step 3)')
    if len(authoritative) > len(winners):
        decisions.append(f'Latest effective date {latest} at equal authority prevails (step 4)')
    conflicts = []
    if any(c['value'] != winner['value'] or c['operator'] != winner['operator'] for c in trusted):
        conflicts.append({'parameter':parameter,'winner':winner['rule_id'],'resolution':decisions,'candidates':[c['rule_id'] for c in trusted]})
    return winner, conflicts

def resolve_rule(db, parameter, as_of, category, tier, reason=None):
    sources = active_sources(db)
    candidates = []
    for raw in db.execute('SELECT * FROM rule_registry WHERE parameter=?', (parameter,)):
        rule = dict(raw)
        source = sources.get(rule['source_doc_id'])
        conditions = json.loads(rule.get('conditions','{}'))
        if not source or not applicable(source, as_of, category, tier) or not applicable(rule, as_of, category, tier):
            continue
        if conditions.get('reason') and conditions['reason'] != reason:
            continue
        rule['source'] = source
        candidates.append(rule)
    # A replacement clause can invalidate an old threshold even when extraction
    # produced no replacement rule. Never continue using that stale threshold.
    for replacement in sources.values():
        if replacement['authority_level'] not in (1,2) or not applicable(replacement,as_of,category,tier):
            continue
        targets=[t.strip() for t in replacement.get('supersedes','').split(';') if t.strip()]
        for target in targets:
            doc,_,clause=target.partition('#')
            old=[c for c in candidates if c['source_doc_id']==doc and (not clause or c['source_section']==clause)]
            new=[c for c in candidates if c['source_doc_id']==replacement['doc_id']]
            if old and not new:
                raise RuleMissing(f'{parameter}: the controlling clause was replaced by {replacement["doc_id"]}, but no validated replacement rule is available')
    return choose(candidates, parameter)
