/* Text assistant. No image calls or autonomous mutations. */
(()=>{
 const style=document.createElement('style');style.textContent=`
 #agent-launch{position:fixed;right:24px;bottom:100px;z-index:6;box-shadow:0 8px 30px #0007}
 #agent-chat{position:fixed;right:16px;top:16px;bottom:16px;width:380px;z-index:8;background:#1c1d22;border:1px solid #ffffff25;border-radius:22px;box-shadow:0 12px 50px #0009;display:flex;flex-direction:column;padding:20px;gap:14px}
 #agent-chat header{height:auto;margin:0;padding:0 0 12px;flex:none}#agent-chat h2{font-size:19px}#agent-chat header button{padding:8px;min-height:36px}
 #agent-messages{flex:1;min-height:60px;overflow:auto;display:flex;flex-direction:column;gap:12px;padding:2px}
 .agent-message{white-space:pre-wrap;overflow-wrap:anywhere;background:#ffffff08;padding:12px;border-radius:14px;line-height:1.7}.agent-message[data-role=user]{background:#7a3c253f;margin-left:20px}.agent-message small{display:block;color:#ffad84;margin-bottom:5px}
 #agent-chat form{display:grid;gap:10px}#agent-chat textarea{width:100%;resize:vertical;min-height:86px;max-height:180px;border:1px solid #ffffff25;border-radius:12px;background:#131418;color:#fff;padding:12px;font:inherit}
 #agent-context{width:auto;min-height:0}#agent-chat .context-label{display:flex;align-items:center;gap:8px}#agent-feedback{font-size:12px;color:#ffb28b;overflow-wrap:anywhere}#agent-status{font-size:12px;color:#bbb}
 @media(min-width:1024px){
 #agent-launch,#agent-close{display:none!important}
 #agent-chat{width:320px;padding:16px;overflow:auto;box-shadow:none}
 body.agent-open main{margin-right:352px;padding-inline:24px}
 body.agent-open .mirror-layout,body.agent-open .profile-layout,body.agent-open .look-layout,body.agent-open .split-layout{grid-template-columns:minmax(0,1fr)}
 body.agent-open .fitting-room,body.agent-open .editor-card{position:static}
 body.agent-open [data-page=closet]{grid-template-columns:minmax(0,1fr)}
 body.agent-open .closet-stats{margin-top:14px}
 body.agent-open #add{grid-template-columns:1fr 1fr}body.agent-open #add button{grid-column:1/-1}
 #agent-chat form{flex:none}
 }
 @media(min-width:1600px){
 #agent-chat{width:380px;padding:20px}
 body.agent-open main{margin-right:412px}
 body.agent-open .mirror-layout,body.agent-open .profile-layout{grid-template-columns:minmax(0,1fr) 280px}
 body.agent-open .look-layout,body.agent-open .split-layout{grid-template-columns:1fr 1fr}
 }
 @media(min-width:1024px) and (max-width:1199px){body.agent-open main{margin-left:144px;padding-inline:16px}.tabs{width:120px;padding-inline:8px}.tabs button{padding-inline:10px;gap:8px}}
 @media(max-width:600px){#agent-chat{inset:8px;width:auto;padding:16px}#agent-launch{right:16px;bottom:100px}}
 `;document.head.append(style);
 const launch=document.createElement('button');launch.id='agent-launch';launch.className='primary';launch.textContent='✦ 穿搭助手';launch.setAttribute('aria-expanded','false');launch.setAttribute('aria-controls','agent-chat');document.body.append(launch);
 const panel=document.createElement('aside');panel.id='agent-chat';panel.hidden=true;panel.setAttribute('aria-label','穿搭助手聊天');panel.innerHTML=`<header><h2>穿搭助手 <small>Agent</small></h2><button type="button" id="agent-close" aria-label="收起聊天">收起</button></header><div id="agent-status">正在检查聊天接口…</div><div id="agent-messages" role="log" aria-label="聊天记录" aria-live="polite"></div><div id="agent-feedback" role="status"></div><form><label for="agent-input">聊聊你的穿搭需求</label><textarea id="agent-input" maxlength="4000" placeholder="例如：明天通勤，想穿得简洁一些"></textarea><label class="context-label"><input id="agent-context" type="checkbox">附带衣橱名称、分类和当前选择（不发照片）</label><small>发送内容将交给已配置的聊天模型；记录保存在当前浏览器。</small><div class="row actions"><button type="button" id="agent-clear">清空对话</button><button type="submit" id="agent-send" class="primary" disabled>发送</button></div></form>`;document.body.append(panel);
 const q=id=>document.getElementById(id);let history=[],storageKey='',busy=false,ready=false;
 function sync(){const next=key+':agent-chat';if(next===storageKey)return;storageKey=next;try{history=JSON.parse(localStorage.getItem(next)||'[]').filter(x=>['user','assistant'].includes(x.role)&&typeof x.content==='string').slice(-40)}catch{history=[]}paint()}
 function paint(){q('agent-messages').replaceChildren();if(!history.length){const intro=document.createElement('p');intro.className='subtle';intro.textContent='可以讨论场景、颜色和搭配思路。目前只提供文字建议，不会自动生成图片或修改衣橱。';q('agent-messages').append(intro)}for(const m of history){const row=document.createElement('div');row.className='agent-message';row.dataset.role=m.role;const label=document.createElement('small');label.textContent=m.role==='user'?'你':'穿搭助手';row.append(label,document.createTextNode(m.content));q('agent-messages').append(row)}q('agent-messages').scrollTop=q('agent-messages').scrollHeight}
 function save(){history=history.slice(-40);try{localStorage.setItem(storageKey,JSON.stringify(history))}catch{q('agent-feedback').textContent='浏览器空间不足，对话未能保存。'}paint()}
 const desktop=window.matchMedia('(min-width:1024px)');
 function close(){if(desktop.matches)return;panel.hidden=true;launch.hidden=false;launch.setAttribute('aria-expanded','false');document.body.classList.remove('agent-open');launch.focus()}
 async function openChat(focus=false){sync();panel.hidden=false;launch.hidden=true;launch.setAttribute('aria-expanded','true');document.body.classList.add('agent-open');if(focus)q('agent-input').focus();try{const r=await fetch('/api/agent/status');if(!r.ok)throw Error();const data=await r.json();ready=data.ready;q('agent-status').textContent=ready?'已连接：'+data.model:'尚未配置 LLM · 生图模型不能代替聊天模型';q('agent-feedback').textContent=ready?'':'请在服务端配置 TRYON_LLM_URL、TRYON_LLM_MODEL 和需要的 TRYON_LLM_KEY。';}catch{ready=false;q('agent-status').textContent='无法连接聊天服务，请稍后重新打开。'}q('agent-send').disabled=!ready||busy};
 launch.onclick=()=>openChat(true);
 function adaptLayout(){if(desktop.matches)openChat();else close()}
 desktop.addEventListener('change',adaptLayout);adaptLayout();
 if(typeof refreshAccount==='function')refreshAccount().then(sync).catch(()=>{});
 q('agent-close').onclick=close;panel.addEventListener('keydown',e=>{if(e.key==='Escape')close()});
 q('agent-clear').onclick=()=>{if(!busy&&confirm('清空当前浏览器身份的聊天记录？')){history=[];save()}};
 panel.querySelector('form').onsubmit=async e=>{e.preventDefault();if(busy||!ready)return;sync();const text=q('agent-input').value.trim();if(!text)return;const requestKey=storageKey;busy=true;q('agent-send').disabled=true;q('agent-clear').disabled=true;q('agent-input').disabled=true;q('agent-feedback').textContent='正在等待模型回复…';
 const pending=[...history,{role:'user',content:text}];const context=q('agent-context').checked?JSON.stringify(state.items.slice(0,50).map(i=>({name:i.name,category:i.category,selected:String(selected[i.category])===String(i.id)}))).slice(0,6000):'';
 try{const response=await fetch('/api/agent/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:pending.slice(-20),context}),signal:AbortSignal.timeout(70000)});const data=await response.json();if(!response.ok)throw Error(data.error||'聊天请求失败');if(key+':agent-chat'!==requestKey){sync();throw Error('浏览器身份已改变，回复未写入当前对话。')}history=[...pending,{role:'assistant',content:data.reply}];q('agent-input').value='';q('agent-feedback').textContent='';save()}catch(error){q('agent-feedback').textContent=error.name==='TimeoutError'?'等待超时，输入已保留，可稍后重试。':error.message}finally{busy=false;q('agent-send').disabled=!ready;q('agent-clear').disabled=false;q('agent-input').disabled=false}
 };
 q('agent-input').addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)&&!e.isComposing){e.preventDefault();panel.querySelector('form').requestSubmit()}});
})();
