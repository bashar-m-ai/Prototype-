import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import path from 'node:path';
export function openDatabase(filename){
 if(filename!==':memory:')fs.mkdirSync(path.dirname(filename),{recursive:true});
 const db=new DatabaseSync(filename);db.exec('PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000;');
 db.exec(`CREATE TABLE IF NOT EXISTS shifts(day TEXT PRIMARY KEY,expected INTEGER,actual INTEGER,opening TEXT DEFAULT '',phase TEXT NOT NULL DEFAULT 'new',created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS notes(id TEXT PRIMARY KEY,day TEXT NOT NULL REFERENCES shifts(day),body TEXT NOT NULL,kind TEXT NOT NULL DEFAULT 'note',created TEXT NOT NULL,source TEXT NOT NULL DEFAULT 'local');
 CREATE INDEX IF NOT EXISTS notes_day ON notes(day,created);
 CREATE TABLE IF NOT EXISTS insights(id TEXT PRIMARY KEY,day TEXT NOT NULL REFERENCES shifts(day),title TEXT NOT NULL,body TEXT NOT NULL,question TEXT NOT NULL,kind TEXT NOT NULL,topic TEXT NOT NULL,evidence TEXT NOT NULL,fingerprint TEXT NOT NULL,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS feedback(insight_id TEXT PRIMARY KEY REFERENCES insights(id),value TEXT NOT NULL,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS answers(id TEXT PRIMARY KEY,day TEXT NOT NULL REFERENCES shifts(day),question_id TEXT NOT NULL,question TEXT NOT NULL,answer TEXT NOT NULL,kind TEXT NOT NULL,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS question_templates(id TEXT PRIMARY KEY,title TEXT NOT NULL,options TEXT NOT NULL,phase TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS product_changes(id TEXT PRIMARY KEY,question_id TEXT NOT NULL,change_type TEXT NOT NULL,detail TEXT NOT NULL,created TEXT NOT NULL);
 PRAGMA user_version=1;`);
 return db;
}
export function ensureShift(db,day){db.prepare('INSERT OR IGNORE INTO shifts(day,created) VALUES (?,?)').run(day,new Date().toISOString())}
export function snapshot(db){return {shifts:db.prepare('SELECT * FROM shifts ORDER BY day DESC').all(),notes:db.prepare('SELECT * FROM notes ORDER BY day,created').all(),insights:db.prepare('SELECT i.*, f.value AS feedback FROM insights i LEFT JOIN feedback f ON f.insight_id=i.id ORDER BY i.created DESC').all().map(i=>({...i,evidence:JSON.parse(i.evidence)})),feedback:db.prepare('SELECT * FROM feedback').all()}}
