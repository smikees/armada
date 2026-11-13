function mcJobReadiness(){
  const value=id=>document.getElementById(id).value;
  const reference=s=>{const [agent,job]=s.split('/');return {agent,job};};
  const from=value('j-window-from'),until=value('j-window-until');
  if(Boolean(from)!==Boolean(until))throw Error('Enter both start-window times, or clear both.');
  const delays=value('j-retry-delays').trim(),fallback=value('j-fallback-job');
  const after=[...document.querySelectorAll('#j-dependencies [data-dependency]')].map(row=>{
    const selected=row.querySelector('[data-job]').value;
    if(!selected)throw Error('Choose a job for every dependency.');
    return {...reference(selected),max_age_minutes:Number(row.querySelector('[data-age]').value),
      outcome:['ok','warn'].filter(k=>row.querySelector('[data-'+k+']').checked)};
  });
  return {requires_connectors:[...document.querySelectorAll('[data-required-connector]:checked')].map(x=>x.value),
    secrets:[...document.querySelectorAll('[data-command-secret]:checked')].map(x=>x.value),
    start_deadline_minutes:Number(value('j-start-deadline')),start_window:from?{from,until}:null,
    after,on_window_end:value('j-window-end'),retry_backoff_seconds:delays?delays.split(',').map(x=>Number(x.trim())):null,
    fallback_job:fallback?reference(fallback):null,coordinator_may_start:document.getElementById('j-coordinator-start').checked,
    coordinator_daily_cap:Number(value('j-coordinator-cap'))};
}
