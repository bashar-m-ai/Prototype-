import {discover} from './memory.mjs';
export function questionsFor(db,day){
 const shift=db.prepare('SELECT * FROM shifts WHERE day=?').get(day);
 const context=discover(db.prepare('SELECT * FROM notes WHERE day < ? ORDER BY day,created').all(day));
 const answers=db.prepare('SELECT * FROM answers WHERE day=? ORDER BY created').all(day);
 const last=Object.fromEntries(answers.map(a=>[a.question_id,a.answer]));
 const topics=new Set(context.map(c=>c.topic));
 const question=(id,title,why,options,kind='observation')=>({id,title,why,options,kind});
 const qs=[];
 if(shift.phase==='opening'){
 if(topics.has('chicory'))qs.push(question('chicory_prep','How’s the chicory prep looking?','You’ve had tight prep here before. Let’s remember your starting point.',['Plenty','Might be tight','Not sure'],'expectation'));
 qs.push(question('gut_feeling','What’s your feeling about tonight?','Your journal compared the forecast with your own hunch. Both are worth keeping.',['Quieter than expected','About right','Busier than expected'],'expectation'));
 }
 if(shift.phase==='live'){
 qs.push(question('pace','How’s service feeling?','One quick check-in.',['Calm','Steady','In a rush']));
 if(last.pace==='In a rush')qs.push(question('rush_start','When did the rush begin?','A rough time is useful. We’ll keep it as an estimate.',['Just now','About 30 minutes ago','Not sure']));
 if(topics.has('chicory'))qs.push(question('chicory_service','How’s the chicory holding up?','Let’s compare what you expected with what’s actually happening.',['Enough so far','Running low','Sold out']));
 if(['Running low','Sold out'].includes(last.chicory_service))qs.push(question('chicory_cause','What seems to be limiting it?','A possible explanation, not a proven cause.',['More orders than expected','Not enough prep','Ingredient ran out'],'hypothesis'));
 if(topics.has('walkins'))qs.push(question('walkins','Any unexpected walk-ins?','Late arrivals showed up in your earlier service notes.',['None so far','A few','More than expected']));
 }
 if(shift.phase==='closed'){
 if(topics.has('peaches'))qs.push(question('peaches_left','Any peaches left after service?','There were more peaches than needed in your journal.',['None left','A little left','A lot left']));
 if(last.peaches_left&&last.peaches_left!=='None left')qs.push(question('peaches_outcome','What happened to the leftovers?','Leftovers and waste are different.',['Used later','Still usable','Wasted']));
 qs.push(question('next_time','What would you change next time?','This becomes a small experiment for the next similar service.',['Prep quantities','Timing or staffing','Nothing yet'],'intention'));
 }
 const templates=db.prepare('SELECT * FROM question_templates').all();
 for(const t of templates){const at=qs.findIndex(q=>q.id===t.id);if(at>=0)qs.splice(at,1);if(t.enabled&&t.phase===shift.phase)qs.push({...question(t.id,t.title,'A question you added or adjusted for this experiment.',JSON.parse(t.options)),custom:true})}
 return qs.filter(q=>!Object.hasOwn(last,q.id));
}
