"""Inventory rules live here, independent of AI and the browser."""
import math
from datetime import date
from storage import one, rows, balance, uid, now

class Conflict(ValueError):
    pass

def text(value, limit=200, required=True):
    if not isinstance(value, str) or len(value.strip()) > limit or (required and not value.strip()):
        raise ValueError('Please enter a short, valid value.')
    return value.strip()

def number(value, optional=False):
    if optional and (value is None or value == ''):
        return None
    if isinstance(value, bool):
        raise ValueError('Enter a positive number.')
    try:
        n = float(value)
    except (ValueError, TypeError):
        raise ValueError('Enter a number.') from None
    if not math.isfinite(n) or n < 0 or n > 1000000:
        raise ValueError('Use a number between 0 and 1,000,000.')
    return n

def day(value):
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        raise ValueError('Choose a valid date.') from None

def log(db, person, kind, message, ref=None, service_day=None):
    db.execute('INSERT INTO activity(person,kind,message,ref,day,created) VALUES (?,?,?,?,?,?)',
               (person, kind, message, ref, service_day or date.today().isoformat(), now()))

def answer(db, person, ref, question, value):
    db.execute('INSERT INTO answers VALUES (?,?,?,?,?,?)', (uid(), person, ref, question, str(value), now()))

def get_item(db, item_id):
    item = one(db, 'SELECT * FROM items WHERE id=?', (item_id,))
    if not item:
        raise ValueError('That ingredient no longer exists. Reopen the menu.')
    return item

def new_batch(db, item, qty, location, use_by=None, opened=None, received=None):
    batch = uid()
    db.execute('INSERT INTO batches VALUES (?,?,?,?,?,?,?)', (batch, item, qty, location, received or now()[:10], opened, use_by))
    return batch

def move(db, person, data):
    item = get_item(db, data.get('item'))
    if data.get('version') != item['version']:
        raise Conflict('Someone updated this stock. Reopen it to see the latest amount before saving.')
    kind = data.get('kind')
    if kind not in ('received', 'made', 'used', 'waste', 'count', 'transfer'):
        raise ValueError('Choose a stock action.')
    if kind == 'made' and item['kind'] != 'prep':
        raise ValueError('Use Received for ingredients.')
    qty = number(data.get('qty'))
    if kind != 'count' and qty <= 0:
        raise ValueError('Enter an amount greater than zero.')
    if not item['known'] and kind in ('used','waste','transfer'):
        raise ValueError('Count the stock first so we have a starting amount.')
    before = balance(db, item['id'])
    location = text(data.get('location', item['location']), 80, False)
    use_by = day(data['use_by']) if data.get('use_by') else None
    opened = day(data['opened']) if data.get('opened') else None
    note = text(data.get('note',''), 1000, False)
    service_day = day(data.get('day', date.today().isoformat()))
    selected = data.get('batch')
    batches = rows(db, 'SELECT * FROM batches WHERE item=? AND qty>0 ORDER BY COALESCE(use_by,\'9999\'),received,id', (item['id'],))
    if selected:
        batches = [b for b in batches if b['id'] == selected]
        if not batches:
            raise ValueError('Choose an available batch.')
    batch_id = None
    if kind in ('received', 'made'):
        batch_id = new_batch(db, item['id'], qty, location, use_by, opened)
    elif kind == 'count':
        # Counts correct a single batch, or create the first known batch. Never erase batch dates.
        if len(batches) > 1 and not selected:
            raise ValueError('There are multiple batches. Choose the batch you counted.')
        if batches:
            batch_id = batches[0]['id']
            db.execute('UPDATE batches SET qty=? WHERE id=?', (qty, batch_id))
        else:
            batch_id = new_batch(db, item['id'], qty, location, use_by, opened)
    else:
        available = sum(b['qty'] for b in batches)
        if qty > available + 0.000001:
            raise Conflict('That is more than the recorded stock. Count it first if the record is wrong.')
        remaining = qty
        for b in batches:
            take = min(b['qty'], remaining)
            db.execute('UPDATE batches SET qty=MAX(0,qty-?) WHERE id=?', (take, b['id']))
            if kind == 'transfer':
                if not location:
                    raise ValueError('Choose the new storage place.')
                new_batch(db, item['id'], take, location, b['use_by'], b['opened'], b['received'])
            remaining -= take
            if remaining < 0.000001:
                break
    after = balance(db, item['id'])
    db.execute('UPDATE items SET known=1,version=version+1 WHERE id=?', (item['id'],))
    db.execute('INSERT INTO movements VALUES (?,?,?,?,?,?,?,?,?,?)',
               (uid(), item['id'], batch_id, kind, round(after-before,6), after, service_day, person, note, now()))
    # First known count is not evidence of consumption. An observed empty closes active estimates.
    if item['known'] and before > 0 and after == 0:
        for p in rows(db, 'SELECT * FROM predictions WHERE item=? AND outcome IS NULL', (item['id'],)):
            elapsed = db.execute('SELECT COUNT(*) FROM services WHERE day>=? AND day<=?', (p['day'], service_day)).fetchone()[0]
            db.execute('UPDATE predictions SET outcome=?,outcome_day=? WHERE id=?', (elapsed, service_day, p['id']))
    name = one(db, 'SELECT name FROM people WHERE id=?', (person,))['name']
    verb = {'received':'received','made':'prepped','used':'used','waste':'logged waste for','count':'counted','transfer':'moved'}[kind]
    log(db, person, 'stock', f"{item['icon']} {name} {verb} {item['name']} · {qty:g} {item['unit']}", item['id'], service_day)

def suggestions(db, today):
    result = []
    closed = [r['day'] for r in rows(db, 'SELECT day FROM services WHERE phase=\'closed\' ORDER BY day DESC LIMIT 7')]
    for item in rows(db, 'SELECT * FROM items ORDER BY name'):
        if not item['known']:
            continue
        qty = balance(db, item['id'])
        rate = None
        if len(closed) >= 2:
            marks = ','.join('?' for _ in closed)
            observations = rows(db, f'SELECT day,SUM(-delta) AS used FROM movements WHERE item=? AND kind=\'used\' AND day IN ({marks}) GROUP BY day', [item['id'], *closed])
            # Missing usage is not zero. Require at least two explicitly logged service totals.
            if len(observations) >= 2:
                rate = sum(r['used'] for r in observations) / len(observations)
        remaining = qty / rate if rate and rate > 0 else None
        if qty == 0 or item['threshold'] is not None and qty <= item['threshold'] or (remaining is not None and item['lead'] is not None and remaining <= item['lead']):
            reason = 'No stock recorded remaining.' if qty == 0 else (f'About {remaining:.1f} services at recent logged usage.' if remaining is not None else 'Below your chosen stock reminder level.')
            result.append({'item':item['id'], 'icon':item['icon'], 'kind':'prep' if item['kind']=='prep' else 'buy', 'title':f"{'Prep' if item['kind']=='prep' else 'Order'} {item['name']}?", 'reason':reason, 'rate':rate, 'remaining':remaining})
        for b in rows(db, 'SELECT * FROM batches WHERE item=? AND qty>0 AND use_by IS NOT NULL AND use_by<=?', (item['id'], today)):
            result.append({'item':item['id'],'icon':item['icon'],'kind':'check','title':f"Check {item['name']}", 'reason':f"Recorded use-by {b['use_by']} · {b['location'] or 'location unknown'}. Check your kitchen procedure; this is not a safety verdict."})
    return result
