"""Tag identity, reviewed collisions and reversible shared metadata merges."""
import hashlib
import json
import unicodedata
import db


def key(value):
    return ' '.join(unicodedata.normalize('NFKC', str(value or '')).casefold().split())


def init(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS entity_redirects(source TEXT PRIMARY KEY,
      target TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE);
    CREATE INDEX IF NOT EXISTS entity_redirect_target ON entity_redirects(target);
    CREATE INDEX IF NOT EXISTS entity_identity ON entities(owner,kind,gender,entity_key(name));
    CREATE INDEX IF NOT EXISTS alias_identity ON aliases(entity_key(name),entity_id);
    ''')
    c.execute('INSERT OR IGNORE INTO migrations VALUES(7,?)', (db.now(),))


def entity_id(c, ident):
    row = c.execute('SELECT target FROM entity_redirects WHERE source=?', (ident,)).fetchone()
    return row[0] if row else ident


def matches(c, name, gender='neutral', exclude=''):
    if gender=='none': gender='neutral'
    rows = c.execute('''SELECT DISTINCT e.*, (SELECT count(*) FROM work_entities we JOIN works w
      ON w.id=we.work_id WHERE we.entity_id=e.id AND w.deleted_at IS NULL) AS uses
      FROM entities e WHERE e.owner=? AND e.kind='tag'
      AND e.gender=? AND e.id<>? AND (entity_key(e.name)=? OR EXISTS
      (SELECT 1 FROM aliases a WHERE a.entity_id=e.id AND entity_key(a.name)=?))
      ORDER BY e.name,e.id''', (db.OWNER, gender, exclude, key(name), key(name)))
    return [db.entity_data(c, r) for r in rows]


def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Conflict(ValueError):
    def __init__(self, conflicts):
        super().__init__('Tag name or alias already belongs to another tag')
        self.conflicts = conflicts
        self.signature = signature(conflicts)


def check(c, data, ident=None):
    if data.get('kind') != 'tag': return []
    old = c.execute('SELECT * FROM entities WHERE id=? AND owner=?', (ident, db.OWNER)).fetchone() if ident else None
    old_aliases = {key(r[0]) for r in c.execute('SELECT name FROM aliases WHERE entity_id=?', (ident,))} if old else set()
    gender = data.get('gender', 'neutral')
    if gender == 'none': gender = 'neutral'
    changed = not old or old['gender'] != gender
    conflicts = []
    canonical = str(data.get('name', '')).strip()
    names = ([canonical] if changed or key(canonical)!=key(old['name']) else [])
    names += [n for n in data.get('aliases', []) if changed or key(n) not in old_aliases]
    for name in dict.fromkeys(names):
        if not key(name): continue
        choices = matches(c, name, gender, ident or '')
        if choices: conflicts.append({'name':name, 'gender':gender, 'choices':choices})
    return conflicts


def save(c, data, ident=None):
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    if ident and not c.execute('SELECT 1 FROM entities WHERE id=? AND owner=?',(ident,db.OWNER)).fetchone():
        raise ValueError('Metadata changed; reload before editing')
    collisions = check(c, data, ident)
    if collisions and (not data.get('allow_collision') or data.get('collision_signature') != signature(collisions)):
        raise Conflict(collisions)
    return db.save_entity(c, data, ident)


def resolve_tags(c, data):
    """Resolve only unambiguous same-attribute tags; leave choices for review."""
    conflicts = []
    for index, item in enumerate(data.get('tag', [])):
        if isinstance(item, str): item = {'name':item}; data['tag'][index] = item
        if item.get('id'):
            row = c.execute("SELECT * FROM entities WHERE id=? AND owner=? AND kind='tag'", (entity_id(c, item['id']), db.OWNER)).fetchone()
            if row: data['tag'][index] = db.entity_data(c, row); continue
            # A deleted chosen tag requires a fresh decision, never an unknown ID.
            item.pop('id', None)
        if item.get('literal_name'): continue
        choices = matches(c, item.get('name'), item.get('gender', 'neutral'))
        if len(choices) == 1: data['tag'][index] = choices[0]
        elif choices: conflicts.append({'index':index, 'kind':'tag', 'name':item['name'], 'gender':item.get('gender', 'neutral'), 'choices':choices})
    return conflicts


def entity_state(c, ident):
    row = c.execute('SELECT * FROM entities WHERE id=? AND owner=?', (ident, db.OWNER)).fetchone()
    if not row: raise ValueError('Metadata not found')
    out = dict(row)
    out['aliases'] = [r[0] for r in c.execute('SELECT name FROM aliases WHERE entity_id=? ORDER BY name', (ident,))]
    return out


def associations(c, ident):
    return [r[0] for r in c.execute('SELECT work_id FROM work_entities WHERE entity_id=? ORDER BY work_id', (ident,))]


def redirects(c, target):
    return dict(c.execute('SELECT source,target FROM entity_redirects WHERE target=? ORDER BY source', (target,)).fetchall())


def merge_preview(c, source, target):
    a, b = entity_state(c, source), entity_state(c, target)
    if source == target or a['kind'] != b['kind']: raise ValueError('Choose different metadata of the same type')
    value = {'source':a, 'target':b, 'source_works':associations(c, source), 'target_works':associations(c, target),
             'source_redirects':redirects(c, source), 'target_redirects':redirects(c, target)}
    return dict(value, signature=signature(value), count=len(value['source_works']))


def merge(c, source, target, expected=None, data=None):
    import features
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    before = merge_preview(c, source, target)
    if expected is not None and expected != before['signature']: raise ValueError('Metadata changed; preview the merge again')
    original = before['source']
    effective = original
    if data:
        if data.get('kind') != original['kind']: raise ValueError('Metadata type cannot change')
        if not str(data.get('name','')).strip(): raise ValueError('Metadata needs a name and valid type')
        effective = dict(original, name=str(data['name']).strip(), aliases=[str(n).strip() for n in data.get('aliases',[]) if str(n).strip()])
    added = set(effective['aliases']) | set(original['aliases']) | {effective['name'],original['name']}
    names = set(before['target']['aliases']) | {n for n in added if key(n) != key(before['target']['name'])}
    c.execute('DELETE FROM aliases WHERE entity_id=?', (target,))
    c.executemany('INSERT INTO aliases VALUES(?,?)', [(target,n) for n in sorted(names)])
    c.execute('INSERT OR IGNORE INTO work_entities SELECT work_id,? FROM work_entities WHERE entity_id=?', (target,source))
    c.execute('UPDATE entity_redirects SET target=? WHERE target=?', (target,source))
    c.execute('DELETE FROM entities WHERE id=?', (source,))
    c.execute('INSERT INTO entity_redirects VALUES(?,?)', (source,target))
    after = {'target':entity_state(c,target), 'target_works':associations(c,target), 'redirects':redirects(c,target)}
    titles = [r[0] for wid in before['source_works'][:20] for r in c.execute('SELECT title FROM works WHERE id=?', (wid,))]
    hid = features.record(c, 'metadata_merge', {'before':before, 'after':after, 'titles':titles})
    return {'ok':True, 'id':target, 'history_id':hid, 'count':before['count']}


def undo_merge(c, payload, apply=False):
    b, a = payload['before'], payload['after']
    source, target = b['source']['id'], b['target']['id']
    if c.execute('SELECT 1 FROM entities WHERE id=?', (source,)).fetchone(): raise ValueError('Merged metadata changed; undo is unavailable')
    current = {'target':entity_state(c,target), 'target_works':associations(c,target), 'redirects':redirects(c,target)}
    if current != a: raise ValueError('Merged metadata or associations changed; undo was cancelled')
    if apply:
        c.execute('DELETE FROM entity_redirects WHERE target=?', (target,))
        for item in (b['source'], b['target']):
            row = {k:v for k,v in item.items() if k!='aliases'}
            columns = list(row)
            if item['id']==source:
                c.execute('INSERT INTO entities('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')', [row[k] for k in columns])
            c.execute('DELETE FROM aliases WHERE entity_id=?', (item['id'],))
            c.executemany('INSERT INTO aliases VALUES(?,?)', [(item['id'],n) for n in item['aliases']])
        c.execute('DELETE FROM work_entities WHERE entity_id=?', (target,))
        for ident, ids in ((source,b['source_works']), (target,b['target_works'])):
            c.executemany('INSERT INTO work_entities VALUES(?,?)', [(wid,ident) for wid in ids])
        c.executemany('INSERT INTO entity_redirects VALUES(?,?)', list(b['source_redirects'].items())+list(b['target_redirects'].items()))
    return {'ok':True, 'kind':'metadata_merge', 'count':b['count'], 'scale':None,
            'merge':{'source':b['source'],'target':b['target']},
            'details':[{'title':b['source']['name']+' → '+b['target']['name'], 'fields':['tag' if b['source']['kind']=='tag' else b['source']['kind']]}]}
