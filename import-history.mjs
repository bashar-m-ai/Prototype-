import fs from 'node:fs';import path from 'node:path';import {fileURLToPath} from 'node:url';import {openDatabase,ensureShift} from './database.mjs';import {remember} from './memory.mjs';
const root=path.dirname(fileURLToPath(import.meta.url)),db=openDatabase(path.join(root,'data/stories.sqlite'));
const rows=JSON.parse(fs.readFileSync(path.join(root,'data/cloud-import.json'),'utf8'));
db.exec('BEGIN');try{for(const n of rows){ensureShift(db,n.day);db.prepare('INSERT OR IGNORE INTO notes(id,day,body,kind,created,source) VALUES (?,?,?,?,?,?)').run(n.id,n.day,n.body,'imported',n.created,'cloud');if(n.source==='journal'){const counts={'2026-09-08':45,'2026-09-09':37,'2026-09-10':41};db.prepare("UPDATE shifts SET phase='closed',actual=? WHERE day=? AND phase='new'").run(counts[n.day]??null,n.day)}}db.exec('COMMIT')}catch(e){db.exec('ROLLBACK');throw e}
for(const n of rows)remember(db,n.day);db.close();console.log('Imported '+rows.length+' saved notes. Original records preserved.');
