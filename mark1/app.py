"""St. Barts Mark 1. Run: python app.py. Production: gunicorn app:app."""
import base64
import hashlib
import json
import os
import secrets
import sqlite3
from datetime import date
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, g
from storage import initialize, connect, one, rows, balance, uid, now, backup
from domain import text, number, day, log, answer, get_item, move, suggestions, Conflict
from intelligence import ask, api_key, AIError, MENU_PROMPT, CONCERN_PROMPT

ROOT = Path(__file__).parent
TABLES = ['people','dishes','items','dish_items','components','batches','services','movements','predictions','tasks','concerns','activity','answers','drafts','shift_details']
UNITS = ['kg','g','L','ml','pieces','portions','batches']

def create_app(data_dir=None):
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    folder = Path(data_dir or os.getenv('DATA_DIR', ROOT / 'data'))
    if os.getenv('RAILWAY_ENVIRONMENT_ID') and not data_dir:
        mount = os.getenv('RAILWAY_VOLUME_MOUNT_PATH')
        if not mount or not folder.resolve().is_relative_to(Path(mount).resolve()):
            raise RuntimeError('Attach a Railway Volume at /data and set DATA_DIR=/data before starting.')
    folder.mkdir(parents=True, exist_ok=True)
    database = str(folder / 'mark1.sqlite')
    initialize(database)
    app.config.update(MAX_CONTENT_LENGTH=13*1024*1024, DATA_DIR=folder, DATABASE=database)

    @app.before_request
    def begin():
        g.db = connect(database)
        g.person = None
        session = request.cookies.get('barts_session','')
        if session:
            g.person = one(g.db, 'SELECT p.* FROM people p JOIN sessions s ON s.person=p.id WHERE s.token=?', (session,))
        if request.method == 'POST':
            origin = request.headers.get('Origin', '')
            allowed = os.getenv('PUBLIC_ORIGIN', request.host_url.rstrip('/'))
            # Railway terminates TLS; compare the browser origin with its configured domain.
            if origin not in (allowed, 'https://' + request.host, 'http://' + request.host if request.host.split(':')[0] in ('localhost','127.0.0.1') else allowed):
                return jsonify(error='Reopen the app and try again.'), 403
            if request.path not in ('/api/join', '/api/key') and not g.person:
                return jsonify(error='Choose your name first.'), 401

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        return response

    @app.teardown_request
    def finish(error):
        if hasattr(g, 'db'):
            g.db.close()

    @app.errorhandler(Conflict)
    def conflict(e):
        return jsonify(error=str(e)), 409

    @app.errorhandler(ValueError)
    def invalid(e):
        return jsonify(error=str(e)), 400

    @app.errorhandler(413)
    def too_large(e):
        return jsonify(error='Choose a smaller image, up to 8 MB.'), 413

    @app.errorhandler(Exception)
    def failed(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return jsonify(error=e.description), e.code
        app.logger.error('Request failed: %s', type(e).__name__)
        return jsonify(error='Could not save. Your input is still here; try again.'), 500

    @app.get('/')
    def index():
        return send_from_directory(ROOT / 'static', 'index.html')

    @app.get('/health')
    def health():
        g.db.execute('SELECT 1')
        return jsonify(ok=True)

    def state():
        today = request.args.get('day', date.today().isoformat())
        day(today)
        public = {'me':g.person, 'people':rows(g.db, '''SELECT p.*,(SELECT MAX(created) FROM activity WHERE person=p.id AND kind!='join') AS last_input,
                    (SELECT message FROM activity WHERE person=p.id AND kind!='join' ORDER BY seq DESC LIMIT 1) AS last_message FROM people p ORDER BY name'''),
                  'aiConnected':bool(api_key(folder)), 'localSetup':not os.getenv('RAILWAY_ENVIRONMENT_ID') and request.remote_addr in ('127.0.0.1','::1'), 'today':today}
        if not g.person:
            return public
        data = {t:rows(g.db, 'SELECT * FROM ' + t + (' ORDER BY seq DESC LIMIT 200' if t == 'activity' else '')) for t in TABLES if t not in ('people','drafts')}
        for i in data['items']:
            i['qty'] = balance(g.db, i['id']) if i['known'] else None
        data['drafts'] = rows(g.db, 'SELECT * FROM drafts WHERE person=? ORDER BY created DESC LIMIT 15', (g.person['id'],))
        data['suggestions'] = suggestions(g.db, today)
        return {**public, **data}

    @app.get('/api/state')
    def get_state():
        return jsonify(state())

    @app.get('/api/history')
    def history():
        if not g.person:
            return jsonify(error='Choose your name first.'),401
        selected=day(request.args.get('day',date.today().isoformat()))
        return jsonify(events=rows(g.db,'SELECT * FROM activity WHERE day=? ORDER BY seq DESC',(selected,)))

    @app.post('/api/join')
    def join():
        n = request.get_json()
        name = text(n.get('name'), 40)
        with g.db:
            p = one(g.db, 'SELECT * FROM people WHERE name=?', (name,))
            if not p:
                p = {'id':uid(), 'name':name}
                g.db.execute('INSERT INTO people VALUES (?,?,?)', (p['id'], name, now()))
            g.db.execute('UPDATE people SET seen=? WHERE id=?', (now(), p['id']))
            token = secrets.token_urlsafe(32)
            g.db.execute('INSERT INTO sessions VALUES (?,?,?)', (token, p['id'], now()))
        response = jsonify(ok=True)
        response.set_cookie('barts_session', token, httponly=True, samesite='Lax', secure=bool(os.getenv('RAILWAY_ENVIRONMENT_ID')) or request.is_secure, max_age=60*60*24*180)
        return response

    @app.post('/api/key')
    def key_setup():
        if os.getenv('RAILWAY_ENVIRONMENT_ID') or request.remote_addr not in ('127.0.0.1','::1'):
            return jsonify(error='Set OPENAI_API_KEY in Railway Variables.'), 403
        key = text(request.get_json().get('key'), 500)
        if not key.startswith('sk-'):
            raise ValueError('Paste an OpenAI API key starting with sk-.')
        path = folder / 'secret.json'
        fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump({'key':key}, f)
        os.chmod(path, 0o600)
        return jsonify(ok=True)

    @app.post('/api/menu/read')
    def read_menu():
        n = request.get_json()
        image = n.get('image')
        content = text(n.get('text',''), 20000, False)
        if image:
            if not isinstance(image, str) or len(image)>12*1024*1024 or not image.startswith(('data:image/jpeg;base64,','data:image/png;base64,','data:image/webp;base64,')):
                raise ValueError('Use a JPEG, PNG or WebP photo up to 8 MB.')
            try:
                raw = base64.b64decode(image.split(',',1)[1], validate=True)
                if len(raw)>8*1024*1024 or not (raw.startswith(b'\xff\xd8\xff') or raw.startswith(b'\x89PNG\r\n\x1a\n') or raw.startswith(b'RIFF') and raw[8:12]==b'WEBP'):
                    raise ValueError()
            except ValueError:
                raise ValueError('That image could not be read. Try a JPEG or PNG.') from None
        if not image and not content:
            raise ValueError('Add a menu photo or paste its text.')
        proposed = ask(folder, MENU_PROMPT, {'menu':content}, image)
        dishes = proposed.get('dishes')
        if not isinstance(dishes,list) or not dishes:
            raise ValueError('Could not read dishes. Try a clearer photo or paste the menu text.')
        clean = []
        for d in dishes[:35]:
            clean.append({'name':text(d.get('name'),120),'icon':text(d.get('icon','🍽️'),12),
                          'ingredients':[{'name':text(i.get('name'),80),'icon':text(i.get('icon','🌱'),12),'kind':'prep' if i.get('kind')=='prep' else 'ingredient'} for i in d.get('ingredients',[])[:12]]})
        draft = uid()
        with g.db:
            g.db.execute('INSERT INTO drafts VALUES (?,?,?,?,?)',(draft,g.person['id'],'menu',json.dumps(clean),now()))
        return jsonify(id=draft,dishes=clean)

    @app.post('/api/concern/preview')
    def preview_concern():
        n = request.get_json()
        body = text(n.get('body'), 600)
        item = get_item(g.db,n['item']) if n.get('item') else None
        context = {'person':g.person['name'], 'concern':body, 'item':item,
                   'quantity':balance(g.db,item['id']) if item and item['known'] else None,
                   'affected_storage': rows(g.db,'SELECT i.name,b.qty,i.unit,b.location,b.use_by FROM batches b JOIN items i ON i.id=b.item WHERE b.qty>0 AND LOWER(b.location)=LOWER(?)',(text(n.get('location',''),80,False),)),
                   'recent':rows(g.db,'SELECT message FROM activity WHERE ref=? ORDER BY seq DESC LIMIT 5',(item['id'],)) if item else []}
        message = ask(folder, CONCERN_PROMPT, context).get('message')
        return jsonify(message=text(message,140))

    @app.post('/api/action')
    def action():
        n = request.get_json()
        action_name = n.get('action')
        request_id = text(n.get('requestId'), 80)
        digest = hashlib.sha256(json.dumps(n,sort_keys=True).encode()).hexdigest()
        db, person = g.db, g.person['id']
        db.execute('BEGIN IMMEDIATE')
        try:
            prior = one(db,'SELECT * FROM requests WHERE id=?',(request_id,))
            if prior:
                if prior['person']!=person or prior['payload']!=digest:
                    raise Conflict('This save already has different content. Reopen and try again.')
                db.rollback()
                return jsonify(ok=True)
            if action_name == 'dish':
                name = text(n.get('name'),120)
                existing = one(db,'SELECT * FROM dishes WHERE name=?',(name,))
                ref = existing['id'] if existing else uid()
                if n.get('id'):
                    if not one(db,'SELECT id FROM dishes WHERE id=?',(n['id'],)):
                        raise ValueError('Dish not found.')
                    ref=n['id']
                    db.execute('UPDATE dishes SET name=?,icon=? WHERE id=?',(name,text(n.get('icon','🍽️'),12),ref))
                elif not existing:
                    db.execute('INSERT INTO dishes VALUES (?,?,?,?)',(ref,name,text(n.get('icon','🍽️'),12),now()))
                log(db,person,'menu',f"🍽️ {g.person['name']} updated {name}",ref)
            elif action_name == 'menu_confirm':
                draft=one(db,'SELECT * FROM drafts WHERE id=? AND person=? AND kind=\'menu\'',(n.get('draft'),person))
                if not draft:
                    raise ValueError('Menu draft not found.')
                selected=n.get('dishes')
                if not isinstance(selected,list) or not 1<=len(selected)<=35:
                    raise ValueError('Choose at least one dish.')
                for d in selected:
                    name=text(d.get('name'),120)
                    db.execute('INSERT OR IGNORE INTO dishes VALUES (?,?,?,?)',(uid(),name,text(d.get('icon','🍽️'),12),now()))
                db.execute('UPDATE drafts SET body=? WHERE id=?',(json.dumps(selected),draft['id']))
                # Keep AI ingredients as proposals until individually confirmed.
                log(db,person,'menu',f"🍽️ {g.person['name']} added the menu. It's taking shape.")
            elif action_name == 'item':
                name=text(n.get('name'),80)
                kind=n.get('kind','ingredient')
                unit=n.get('unit','kg')
                if kind not in ('ingredient','prep') or unit not in UNITS:
                    raise ValueError('Choose an ingredient type and unit.')
                old=one(db,'SELECT * FROM items WHERE name=?',(name,))
                if old:
                    ref=old['id']
                    if old['unit']!=unit:
                        raise ValueError(f"{name} already uses {old['unit']}. Select that unit to share its stock.")
                else:
                    ref=uid()
                    db.execute('INSERT INTO items(id,name,icon,kind,unit,created) VALUES (?,?,?,?,?,?)',(ref,name,text(n.get('icon','🌱'),12),kind,unit,now()))
                if n.get('dish'):
                    db.execute('INSERT OR IGNORE INTO dish_items VALUES (?,?)',(n['dish'],ref))
                if n.get('parent'):
                    parent=get_item(db,n['parent'])
                    if parent['kind']!='prep':
                        raise ValueError('Only prepared components have ingredients.')
                    descendants=rows(db,'WITH RECURSIVE child(id) AS (SELECT child FROM components WHERE parent=? UNION SELECT c.child FROM components c JOIN child ON c.parent=child.id) SELECT id FROM child',(ref,))
                    if parent['id']==ref or parent['id'] in [d['id'] for d in descendants]:
                        raise ValueError('A component cannot contain itself.')
                    db.execute('INSERT OR IGNORE INTO components VALUES (?,?)',(parent['id'],ref))
                answer(db,person,ref,'Which ingredient or prep belongs here?',name)
                log(db,person,'menu',f"{n.get('icon','🌱')} {g.person['name']} added {name}",ref)
            elif action_name == 'item_settings':
                i=get_item(db,n.get('item'))
                if i['version']!=n.get('version'):
                    raise Conflict('This ingredient changed. Reopen it before saving.')
                loc=text(n.get('location',i['location']),80,False)
                lead=number(n.get('lead',i['lead']),True)
                threshold=number(n.get('threshold',i['threshold']),True)
                db.execute('UPDATE items SET location=?,lead=?,threshold=?,version=version+1 WHERE id=?',(loc,lead,threshold,i['id']))
                answer(db,person,i['id'],'Storage, restock interval and reminder level',json.dumps({'location':loc,'lead':lead,'threshold':threshold}))
                log(db,person,'stock',f"{i['icon']} {g.person['name']} updated tracking for {i['name']}",i['id'])
            elif action_name == 'movement':
                move(db,person,n)
            elif action_name == 'prediction':
                i=get_item(db,n.get('item'))
                duration=number(n.get('services'))
                if not i['known'] or duration<=0:
                    raise ValueError('Count the stock and choose how many services it should last.')
                db.execute('INSERT INTO predictions VALUES (?,?,?,?,?,?,?,?,?,?)',(uid(),i['id'],balance(db,i['id']),duration,'user',day(n['day']),person,None,None,now()))
                answer(db,person,i['id'],'How many services will this last?',duration)
                log(db,person,'estimate',f"{i['icon']} {g.person['name']} expects {i['name']} to last {duration:g} services",i['id'])
            elif action_name == 'service':
                service_day=day(n.get('day'))
                phase=n.get('phase','live')
                if phase not in ('live','closed'):
                    raise ValueError('Choose a service phase.')
                covers=number(n.get('covers'),True)
                if covers is not None and not covers.is_integer():
                    raise ValueError('Use whole covers.')
                db.execute('INSERT OR IGNORE INTO services(day) VALUES (?)',(service_day,))
                field='actual' if phase=='closed' else 'expected'
                db.execute(f'UPDATE services SET {field}=?,phase=? WHERE day=?',(covers,phase,service_day))
                log(db,person,'service',f"{'🌙' if phase=='closed' else '👋'} {g.person['name']} {'closed the service' if phase=='closed' else 'joined the service'}",service_day,service_day)
            elif action_name == 'past_shift':
                service_day=day(n.get('day'))
                if service_day>date.today().isoformat():
                    raise ValueError('Choose today or an earlier date for a past shift.')
                prior=one(db,'SELECT * FROM shift_details WHERE day=?',(service_day,))
                if (prior['version'] if prior else 0)!=n.get('version',0):
                    raise Conflict('Someone edited this shift. Reopen it before saving.')
                counts={k:number(n.get(k),True) for k in ('expected','actual','reservations','walkins')}
                if any(v is not None and not v.is_integer() for v in counts.values()):
                    raise ValueError('Use whole numbers for people and reservations.')
                tags=n.get('tags',[])
                allowed=['Running low','Sold out','Unexpected rush','Station overloaded','Prep shortage','Over-prepared','Waste']
                if not isinstance(tags,list) or any(t not in allowed for t in tags):
                    raise ValueError('Choose valid observation tags.')
                db.execute("INSERT INTO services(day,expected,actual,phase) VALUES (?,?,?,'closed') ON CONFLICT(day) DO UPDATE SET expected=excluded.expected,actual=excluded.actual",
                           (service_day,counts['expected'],counts['actual']))
                values=(service_day,counts['reservations'],counts['walkins'],text(n.get('rush',''),100,False),text(n.get('weather',''),100,False),text(n.get('terrace',''),100,False),text(n.get('prep',''),4000,False),json.dumps(list(dict.fromkeys(tags))),text(n.get('events',''),3000,False),text(n.get('note',''),5000,False),person,(prior['version']+1 if prior else 1),now())
                db.execute('INSERT INTO shift_details VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(day) DO UPDATE SET reservations=excluded.reservations,walkins=excluded.walkins,rush=excluded.rush,weather=excluded.weather,terrace=excluded.terrace,prep=excluded.prep,tags=excluded.tags,events=excluded.events,note=excluded.note,person=excluded.person,version=excluded.version,updated=excluded.updated',values)
                answer(db,person,service_day,'Past shift details',json.dumps(n))
                log(db,person,'past_shift',f"🌙 {g.person['name']} {'updated' if prior else 'remembered'} the {service_day} shift",service_day,service_day)
            elif action_name == 'note':
                log(db,person,'note',text(n.get('body'),2000),None,day(n['day']))
            elif action_name == 'task':
                item=get_item(db,n.get('item'))
                kind='prep' if item['kind']=='prep' else 'buy'
                ref=uid()
                if not one(db,'SELECT id FROM tasks WHERE item=? AND status=\'open\'',(item['id'],)):
                    db.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?,?)',(ref,item['id'],kind,text(n.get('body',item['name']),200),'open',person,now()))
                    estimate = next((s for s in suggestions(db,date.today().isoformat()) if s['item']==item['id'] and s.get('remaining') is not None),None)
                    if estimate and estimate['remaining']>0:
                        db.execute('INSERT INTO predictions VALUES (?,?,?,?,?,?,?,?,?,?)',(uid(),item['id'],balance(db,item['id']),estimate['remaining'],'logged_usage',date.today().isoformat(),person,None,None,now()))
                    log(db,person,'task',f"{item['icon']} {g.person['name']} added {item['name']} to {'prep' if kind=='prep' else 'ordering'}",ref)
            elif action_name == 'task_done':
                task=one(db,'SELECT * FROM tasks WHERE id=?',(n.get('id'),))
                if not task:
                    raise ValueError('Task not found.')
                db.execute('UPDATE tasks SET status=\'done\' WHERE id=?',(task['id'],))
                log(db,person,'task',f"✓ {g.person['name']} marked {task['body']} done",task['id'])
            elif action_name == 'concern':
                body=text(n.get('body'),600)
                message=text(n.get('message'),140)
                item=n.get('item') or None
                if item:
                    get_item(db,item)
                location=text(n.get('location',''),80,False)
                ref=uid()
                db.execute('INSERT INTO concerns VALUES (?,?,?,?,?,?,?,?,?,?)',(ref,body,message,item,location,person,None,'open','',now()))
                log(db,person,'concern',message,ref)
            elif action_name == 'concern_update':
                c=one(db,'SELECT * FROM concerns WHERE id=?',(n.get('id'),))
                if not c:
                    raise ValueError('Concern not found.')
                status=n.get('status')
                if status not in ('checking','resolved','open'):
                    raise ValueError('Choose a concern status.')
                resolution=text(n.get('resolution',''),600,status=='resolved')
                if status=='checking' and c['owner'] and c['owner']!=person:
                    raise Conflict('Someone already picked this up. Add an update instead.')
                db.execute('UPDATE concerns SET status=?,owner=COALESCE(owner,?),resolution=? WHERE id=?',(status,person,resolution,c['id']))
                log(db,person,'concern',f"{'✓' if status=='resolved' else '💬'} {g.person['name']}: {resolution or 'I’ll check this.'}",c['id'])
            else:
                raise ValueError('Unknown action.')
            db.execute('INSERT INTO requests VALUES (?,?,?,?)',(request_id,person,digest,now()))
            db.execute('UPDATE people SET seen=? WHERE id=?',(now(),person))
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            raise ValueError('That name is already in use, or a linked record changed. Reopen and try again.') from None
        except Exception:
            db.rollback()
            raise
        return jsonify(ok=True)

    @app.get('/api/export')
    def export():
        if not g.person:
            return jsonify(error='Choose your name first.'),401
        data={t:rows(g.db,'SELECT * FROM '+t) for t in TABLES}
        return jsonify(format='st-barts-mark1',exported=now(),**data)

    @app.post('/api/backup')
    def manual_backup():
        backup(database)
        return jsonify(ok=True)

    return app

app=create_app()
if __name__=='__main__':
    app.run(host=os.getenv('HOST','127.0.0.1'),port=int(os.getenv('PORT',4190)),debug=False)
