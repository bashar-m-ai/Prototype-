import { createHash,randomUUID } from 'node:crypto';
const normal=s=>s.toLowerCase().replace(/\s+/g,' ').trim();
export function uniqueNotes(notes){const seen=new Set();return [...notes].sort((a,b)=>a.day.localeCompare(b.day)).filter(n=>{const k=normal(n.body);if(seen.has(k))return false;seen.add(k);return true})}
export function discover(notes){
 const all=uniqueNotes(notes).filter(n=>!['expected','expectation','hypothesis','intention'].includes(n.kind)&&!n.body.endsWith(' Skipped')), groups=[];
 const chicory=all.filter(n=>n.body.split('\n').some(l=>/chicory|chikery|chikory|chikery/i.test(l)&&/low|ran out|sold out|barely|tight|short|needed more|not enough/i.test(l)));
 const peaches=all.filter(n=>n.body.split('\n').some(l=>/peach/i.test(l)&&/more.*need|left|waste|too many|over/i.test(l)));
 const walkins=all.filter(n=>/late walk[ -]?ins/i.test(n.body));
 if(chicory.length)groups.push({topic:'chicory',title:'Keep an eye on chicory.',body:`${new Set(chicory.map(n=>n.day)).size>1?'More than one service mentions':'A previous note mentions'} chicory being tight or running out. That is worth watching, but it does not tell us how much extra to prep.`,question:'How many chicory portions did you prep today?',evidence:chicory.map(n=>n.id)});
 if(peaches.length)groups.push({topic:'peaches',title:'What happened to the peaches?',body:'Your notes mention more peaches than needed. Leftover prep and actual waste are different; we still need the quantities and what happened next.',question:'Were the leftover peaches used later or thrown away?',evidence:peaches.map(n=>n.id)});
 if(walkins.length)groups.push({topic:'walkins',title:'Leave room for the unexpected.',body:'You mentioned late walk-ins before. There is not enough evidence to predict them yet.',question:'When did the last walk-ins arrive tonight?',evidence:walkins.map(n=>n.id)});
 return groups;
}
export function remember(db,day){
 const shift=db.prepare('SELECT * FROM shifts WHERE day=?').get(day);
 const notes=db.prepare('SELECT * FROM notes WHERE day<=? ORDER BY day,created').all(day);
 const current=notes.filter(n=>n.day===day);
 const fingerprint=createHash('sha256').update(JSON.stringify({shift,notes:notes.map(n=>[n.id,n.body])})).digest('hex');
 const existing=db.prepare('SELECT * FROM insights WHERE day=? AND fingerprint=? AND kind=?').get(day,fingerprint,'local');if(existing)return existing;
 const latest=current.at(-1);
 const custom=[];
 for(const q of db.prepare("SELECT * FROM question_templates WHERE enabled=1 AND id LIKE 'custom_%'").all()){
 const responses=db.prepare("SELECT * FROM answers WHERE question_id=? AND answer=? AND day<=? ORDER BY day").all(q.id,JSON.parse(q.options)[2],day);
 if(responses.length)custom.push({topic:q.id,title:'Something you chose to watch.',body:`For “${q.title}”, you selected “${JSON.parse(q.options)[2]}” on ${new Set(responses.map(r=>r.day)).size} service(s). That is an observation to explore, not an explanation yet.`,question:'What would help you understand this next time?',evidence:responses.map(r=>r.id)});
 }
 const candidates=[...discover(notes),...custom].filter(c=>!db.prepare("SELECT 1 FROM insights i JOIN feedback f ON f.insight_id=i.id WHERE i.topic=? AND f.value='not-useful'").get(c.topic));
 let suggestion=candidates.find(c=>latest&&c.evidence.includes(latest.id))||candidates[0];
 const answers=db.prepare('SELECT * FROM answers WHERE day=? ORDER BY created').all(day);
 const prep=answers.find(a=>a.question_id==='chicory_prep'),outcome=answers.find(a=>a.question_id==='chicory_service');
 if(prep&&outcome&&['Running low','Sold out'].includes(outcome.answer)&&latest?.id===outcome.id)suggestion={topic:'prep-outcome',title:prep.answer==='Might be tight'?'Your prep concern showed up.':'A useful surprise to investigate.',body:`Before service you said “${prep.answer}”. During service you reported “${outcome.answer}”. We have an expectation and an outcome to compare, but still need prep and order quantities to understand why.`,question:'What seems to be limiting the chicory?',evidence:[prep.id,outcome.id]};
 if(shift.phase==='closed'&&shift.actual!==null&&shift.expected!==null&&latest?.kind==='actual'){const diff=shift.actual-shift.expected;suggestion={topic:'covers',title:diff===0?'Your expectation matched.':diff>0?'Busier than you expected.':'Quieter than you expected.',body:`You expected ${shift.expected} covers and recorded ${shift.actual}. ${diff===0?'That says something about turnout; prep still needs its own evidence.':'That is a difference of '+Math.abs(diff)+'. It does not explain the cause on its own.'}`,question:'What would you do differently with the same turnout?',evidence:current.filter(n=>n.kind==='expected'||n.kind==='actual').map(n=>n.id)}}
 if(!suggestion&&latest){const body=latest.body;
 if(/running low|ran out|sold out|shortage/i.test(body))suggestion={topic:'shortage',title:'Let’s catch the useful detail.',body:'You noticed a shortage. The amount prepared will help us understand it later.',question:'Roughly how much did you start with?',evidence:[latest.id]};
 else if(/rush|overload|busy/i.test(body))suggestion={topic:'rush',title:'A moment worth remembering.',body:'This sounds like a pressure point in service. A time and a station would give it useful context.',question:'When did it start getting busy?',evidence:[latest.id]};
 else if(/waste|over.prep|left over/i.test(body))suggestion={topic:'waste',title:'Let’s separate leftovers from waste.',body:'What remains after service may still be usable. We should not count it as waste without checking.',question:'How much was actually thrown away?',evidence:[latest.id]};
 else suggestion={topic:'observation',title:'Got it. Keep going.',body:'This observation is saved with tonight’s story. We can come back to it after service.',question:'',evidence:[latest.id]};}
 if(!suggestion)suggestion={topic:'first',title:'We’ll find out together.',body:'Start with what you expect. As you add observations, they become the evidence for the next service.',question:'',evidence:[]};
 const row={id:randomUUID(),day,...suggestion,kind:'local',fingerprint,created:new Date().toISOString()};
 db.prepare('INSERT INTO insights(id,day,title,body,question,kind,topic,evidence,fingerprint,created) VALUES (?,?,?,?,?,?,?,?,?,?)').run(row.id,day,row.title,row.body,row.question,row.kind,row.topic,JSON.stringify(row.evidence),fingerprint,row.created);return row;
}
