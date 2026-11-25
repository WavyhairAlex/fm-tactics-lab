'use strict';

const historyBaselines=new Map();

function completedMatchResult(job){
 return job?.status==='complete'&&Number.isFinite(job.metrics?.B?.win_rate)&&job.metrics.B.n>0;
}

function historyBaseline(job, jobs, choice){
 if(!completedMatchResult(job)||choice===false)return null;
 const candidates=jobs.filter(other=>other.id!==job.id&&completedMatchResult(other)
  &&(other.experiment_type||'match')===(job.experiment_type||'match'));
 if(choice)return candidates.find(other=>other.id===choice)||null;
 if(!job.comparison_context)return null;
 return candidates.filter(other=>other.created<job.created
  &&other.comparison_context?.settings===job.comparison_context.settings)
  .sort((a,b)=>b.created-a.created)[0]||null;
}

function resultDelta(value, base, digits, suffix='', lowerIsBetter=false, comparable=true){
 if(!Number.isFinite(value)||!Number.isFinite(base))return '';
 const delta=Number((value-base).toFixed(digits));
 const tone=!comparable||!delta?'neutral':(delta>0)!==lowerIsBetter?'up':'down';
 return `<small class="metric-delta ${tone}">${delta>0?'+':''}${delta.toFixed(digits)}${suffix}</small>`;
}

function tacticSnapshotLabel(job, group){
 const snapshot=job.tactic_snapshots?.[group];
 const legacy=job.experiment_type==='save_opponents'?null:job.variant_names?.[group];
 const name=snapshot?.name||legacy;
 const label=group==='A'?'对照 A':'本次 B';
 const title=name?`<strong translate="no">${esc(name)}</strong>`:
  `<strong>${snapshot?'手动战术':'旧记录无战术名称'}</strong>`;
 return `<div class="tactic-snapshot"><small>${label}</small>${title}${
  snapshot?.team?`<span translate="no">${esc(snapshot.team)}</span>`:''
 }${snapshot?.opponent?`<span>对手 <span translate="no">${esc(snapshot.opponent.name||snapshot.opponent.team||'')}</span></span>`:''}</div>`;
}

function experimentOverview(job){
 if(job.attribute_screen||job.tactical_screen)return '';
 const compare=isComparison(job),a=job.tactic_snapshots?.A,b=job.tactic_snapshots?.B;
 const sameName=compare&&a?.strategy&&b?.strategy&&a.name===b.name;
 const snapshotNote=sameName?`<p class="tiny muted tactic-snapshot-note">${a.strategy===b.strategy?
  'A、B 的战术设置相同':'A、B 同名，战术设置有改动'}</p>`:'';
 const snapshots=`<div class="tactic-snapshots">${compare?tacticSnapshotLabel(job,'A'):''}
  ${tacticSnapshotLabel(job,'B')}</div>${snapshotNote}`;
 if(job.experiment_type==='setpiece_episode'||!job.metrics?.B)return snapshots;
 const choice=historyBaselines.get(job.id);
 const baseline=historyBaseline(job,history,choice);
 const current=job.metrics.B, previous=baseline?.metrics.B;
 const settings=job.comparison_context?.settings;
 const comparable=!!settings&&baseline?.comparison_context?.settings===settings;
 const sameSample=comparable&&baseline.comparison_context.sample===job.comparison_context.sample;
 const difference=(value,base,digits,suffix='',lowerIsBetter=false)=>previous?
  resultDelta(value,base,digits,suffix,lowerIsBetter,comparable):'';
 const side=job.experiment_type==='save_opponents'?'己方胜率':'主队胜率';
 const scope=careerResultScope(job);
 const mode=baseline?(sameSample?'相同种子及对手样本':comparable?'不同种子或对手抽样，按独立结果比较':
  '比赛设置不同或旧记录缺少校验信息'):'';
 const details=baseline?`<span>历史对照 <b translate="no">${esc(baseline.name||baseline.id)}</b>
  · 本次 ${current.n} 场／历史 ${previous.n} 场 · ${mode}</span>`:'';
 const controls=completedMatchResult(job)?`<div class="history-compare">${details}
  <button type="button" class="button small" id="choose-history-baseline">选择历史对照</button></div>`:'';
 return `${scope?`<h3 class="result-round-scope">主统计 · ${scope}</h3>`:''}
  <div class="metric-grid">
   <div class="card metric"><small>${side}</small><strong>${pct(current.win_rate)}${difference(current.win_rate*100,previous?.win_rate*100,1,' 个百分点')}</strong>
    <div class="sub">95% 区间 ${pct(current.win_interval[0])} — ${pct(current.win_interval[1])}</div></div>
   <div class="card metric"><small>胜 / 平 / 负</small><strong>${current.wins} <span class="muted">/ ${current.draws} / ${current.losses}</span></strong>
    <div class="sub">${current.n} 场有效完整比赛</div></div>
   <div class="card metric"><small>场均进球 / 失球</small><strong>${fmt(current.goals_for)}${difference(current.goals_for,previous?.goals_for,2)}
    <span class="muted">/ ${fmt(current.goals_against)}</span>${difference(current.goals_against,previous?.goals_against,2,'',true)}</strong></div>
   <div class="card metric"><small>场均积分</small><strong>${fmt(current.points)}${difference(current.points,previous?.points,2)}</strong>
    <div class="sub">胜 3 分 · 平 1 分</div></div>
  </div>${snapshots}${controls}`;
}

function openExperimentPicker(baseline){
 const id=selectedJob.id;
 const jobs=baseline?history.filter(job=>historyBaseline(selectedJob,[job],job.id)):history;
 const choice=historyBaselines.get(id);
 const dialog=document.createElement('dialog');
 dialog.className='experiment-picker';
 dialog.innerHTML=`<h2>${baseline?'选择历史对照':'历史实验'}</h2>
  <input type="search" aria-label="查找实验" placeholder="按名称搜索" data-filter>
  ${baseline?`<div class="experiment-picker-options">
   <button type="button" class="button small ${choice===undefined?'active':''}" data-baseline="auto">自动选最近的同设置实验</button>
   <button type="button" class="button small ${choice===false?'active':''}" data-baseline="off">关闭历史对照</button></div>`:''}
  <div class="experiment-picker-list">${jobs.map(job=>`<button type="button" class="button ${job.id===(baseline?choice:id)?'active':''}" data-experiment="${esc(job.id)}">
   <span translate="no">${esc(job.name||job.id)}</span><small>${job.completed} / ${job.total} · ${new Date(job.created*1000).toLocaleString(window.FM27I18n.language)}</small></button>`).join('')||'<p>没有可选择的实验</p>'}</div>
  <div class="dialog-actions"><button type="button" class="button" data-close>关闭</button></div>`;
 const entries=[...dialog.querySelectorAll('[data-experiment]')];
 dialog.querySelector('[data-filter]').oninput=event=>{
  const text=event.target.value.trim().toLocaleLowerCase();
  entries.forEach(button=>button.hidden=!button.textContent.toLocaleLowerCase().includes(text));
 };
 const applyChoice=value=>{
  if(value===undefined)historyBaselines.delete(id);else historyBaselines.set(id,value);
  dialog.close();
  render();
 };
 for(const button of dialog.querySelectorAll('[data-baseline]')){
  button.onclick=()=>applyChoice(button.dataset.baseline==='auto'?undefined:false);
 }
 for(const button of entries)button.onclick=async()=>{
  if(baseline)return applyChoice(button.dataset.experiment);
  entries.forEach(entry=>entry.disabled=true);
  try{
   const result=await api('/api/jobs/'+button.dataset.experiment);
   if(!dialog.open)return;
   selectedJob=result;
   dialog.close();
   render();
   window.scrollTo(0,0);
  }catch(error){toast(error.message);entries.forEach(entry=>entry.disabled=false);}
 };
 dialog.querySelector('[data-close]').onclick=()=>dialog.close();
 dialog.onclose=()=>dialog.remove();
 document.body.append(dialog);
 dialog.showModal();
}

const historyPickerBind=bind;
bind=function(){
 historyPickerBind();
 const button=$('#open-experiment-history');
 if(button)button.onclick=()=>openExperimentPicker(false);
 const baseline=$('#choose-history-baseline');
 if(baseline)baseline.onclick=()=>openExperimentPicker(true);
};
