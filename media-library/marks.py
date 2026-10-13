"""Five independent work marks; bit 1 mirrors legacy purchase status."""
import db

SYMBOLS = [('○','●'),('△','▲'),('□','■'),('♡','♥'),('☆','★')]

def numbers(bits): return [n for n in range(1,6) if bits & (1 << (n-1))]

def bits(values):
    if not isinstance(values,list) or any(type(n)!=int or not 1<=n<=5 for n in values):
        raise ValueError('Choose mark numbers 1–5')
    return sum(1 << (n-1) for n in set(values))

def init(c):
    if 'mark_bits' not in {r['name'] for r in c.execute('PRAGMA table_info(works)')}:
        c.execute("ALTER TABLE works ADD COLUMN mark_bits INTEGER NOT NULL DEFAULT 0 CHECK(typeof(mark_bits)='integer' AND mark_bits BETWEEN 0 AND 31)")
        c.execute('UPDATE works SET mark_bits=CASE WHEN bought<>0 THEN 1 ELSE 0 END')
    c.executescript('''
    CREATE TABLE IF NOT EXISTS mark_labels(owner TEXT NOT NULL REFERENCES owners(id), number INTEGER NOT NULL CHECK(number BETWEEN 1 AND 5), label TEXT NOT NULL DEFAULT '', PRIMARY KEY(owner,number));
    CREATE TRIGGER IF NOT EXISTS purchase_to_mark AFTER UPDATE OF bought ON works
    WHEN NEW.bought <> (NEW.mark_bits & 1)
    BEGIN UPDATE works SET mark_bits=(mark_bits & 30) | CASE WHEN NEW.bought<>0 THEN 1 ELSE 0 END WHERE id=NEW.id; END;
    CREATE TRIGGER IF NOT EXISTS mark_to_purchase AFTER UPDATE OF mark_bits ON works
    WHEN NEW.bought <> (NEW.mark_bits & 1)
    BEGIN UPDATE works SET bought=NEW.mark_bits & 1 WHERE id=NEW.id; END;
    CREATE TRIGGER IF NOT EXISTS purchase_mark_insert AFTER INSERT ON works
    WHEN NEW.bought <> (NEW.mark_bits & 1)
    BEGIN UPDATE works SET mark_bits=(mark_bits & 30) | CASE WHEN NEW.bought<>0 THEN 1 ELSE 0 END WHERE id=NEW.id; END;
    ''')
    for n in range(1,6): c.execute('INSERT OR IGNORE INTO mark_labels(owner,number) SELECT id,? FROM owners',(n,))
    c.execute('INSERT OR IGNORE INTO migrations VALUES(8,?)',(db.now(),))

def definitions(c):
    rows={r['number']:r['label'] for r in c.execute('SELECT number,label FROM mark_labels WHERE owner=?',(db.OWNER,))}
    return [{'number':n,'label':rows.get(n,''),'off':SYMBOLS[n-1][0],'on':SYMBOLS[n-1][1]} for n in range(1,6)]

def save_labels(c,data):
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    labels=data.get('labels')
    if not isinstance(labels,list) or len(labels)!=5 or any(not isinstance(v,str) or len(v)>80 for v in labels): raise ValueError('Enter five mark labels, up to 80 characters each')
    if data.get('expected')!=[d['label'] for d in definitions(c)]: raise ValueError('Mark labels changed; reload before saving')
    for n,label in enumerate(labels,1): c.execute('INSERT INTO mark_labels VALUES(?,?,?) ON CONFLICT(owner,number) DO UPDATE SET label=excluded.label',(db.OWNER,n,label.strip()))
    return definitions(c)

def toggle(c,wid,data):
    import features
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    n,value=data.get('number'),data.get('value')
    if type(n)!=int or not 1<=n<=5 or type(value)!=bool: raise ValueError('Choose mark numbers 1–5')
    w=db.get_work(c,wid)
    current=bits(w['marks']); flag=1<<(n-1)
    wanted=(current|flag) if value else (current & ~flag)
    if current==wanted: return w
    if bits(data.get('expected'))!=current: raise ValueError('Marks changed; reload before saving')
    before=features.state(c,wid)
    c.execute('UPDATE works SET mark_bits=?,updated=? WHERE id=? AND owner=?',(wanted,db.now(),wid,db.OWNER))
    features.record(c,'edit',{'works':{wid:features.changes(before,features.state(c,wid))},'titles':[w['title']]})
    return db.get_work(c,wid)
