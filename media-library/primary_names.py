"""Primary metadata names, preserving IDs and every former primary as an alias."""
import db


def normalize(c, data, ident=None):
    value = dict(data)
    old = c.execute('SELECT * FROM entities WHERE id=? AND owner=?', (ident, db.OWNER)).fetchone() if ident else None
    name = str(value.get('name', '')).strip()
    aliases = {str(n).strip() for n in value.get('aliases', []) if str(n).strip()}
    # Accept older clients, but persist a real primary name rather than a display override.
    selected = str(value.get('display_alias', '')).strip()
    if selected:
        if selected != name and selected not in aliases and not (old and old['display_alias']==selected):
            raise ValueError('Choose a primary name from the names and aliases')
        aliases.add(name)
        name = selected
    if old and old['name'] != name:
        aliases.add(old['name'])
    if old and old['display_alias'] and old['display_alias'] != name:
        aliases.add(old['display_alias'])
    aliases.discard(name)
    aliases.discard('')
    value.update(name=name, aliases=sorted(aliases), display_alias='')
    return value


def migrate(c):
    if c.execute('SELECT 1 FROM migrations WHERE version=14').fetchone(): return
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    rows = [dict(r) for r in c.execute('SELECT * FROM entities')]
    moving = {r['id'] for r in rows if r['display_alias'] and r['display_alias'] != r['name']}
    # Freeze ambiguous groups instead of silently merging separately curated records.
    # Repeat because a frozen original name may block another promotion. Cycles are valid.
    while True:
        groups = {}
        for row in rows:
            name = row['display_alias'] if row['id'] in moving else row['name']
            groups.setdefault((row['owner'], row['kind'], row['gender'], name), []).append(row['id'])
        blocked = {ident for ids in groups.values() if len(ids)>1 for ident in ids} & moving
        if not blocked: break
        moving -= blocked
    # Two phases permit exchanging names without transient UNIQUE constraint failures.
    for row in rows:
        if row['id'] in moving:
            c.execute('UPDATE entities SET name=? WHERE id=?', ('__folio_primary_'+db.uid(), row['id']))
    for row in rows:
        if row['id'] in moving:
            c.execute('INSERT OR IGNORE INTO aliases VALUES(?,?)', (row['id'], row['name']))
            c.execute('DELETE FROM aliases WHERE entity_id=? AND name=?', (row['id'], row['display_alias']))
            c.execute("UPDATE entities SET name=?,display_alias='' WHERE id=?", (row['display_alias'], row['id']))
        elif row['display_alias'] == row['name']:
            c.execute("UPDATE entities SET display_alias='' WHERE id=?", (row['id'],))
    c.execute('INSERT INTO migrations VALUES(14,?)', (db.now(),))
