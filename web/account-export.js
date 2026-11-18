/* Account-scoped avatar library, phone login and branded image exports. */
'use strict';
let account = {loaded:false,user:null,quota:null,avatars:[],sms_ready:false};
let accountSequence=0, accountTimer, codeTimer, codeUntil=0, savingAvatar=false;
let branding={brand:'AI 私人衣橱',qr_url:null,download_url:null,pending_label:'APP 即将上线'};
let preparedExport=null;
const remoteAvatarId=id=>typeof id==='string'&&/^[a-f0-9]{32}$/.test(id);
function freshState(){return {items:[],looks:[],avatars:[]}}
function ensureLocalLibrary(){
 if(!Array.isArray(state.avatars))state.avatars=[];
 if(state.avatar&&!state.avatarId&&!state.avatar.startsWith('/api/avatars/')){
  const id=crypto.randomUUID();state.avatars.push({id,kind:state.avatarKind||'photo',image:state.avatar,settings:state.avatarSettings||null,created:Date.now()/1000});state.avatarId=id;
 }
}
function switchAccountState(user,associateGuest=false){
 const nextKey=user?baseStorageKey+':'+user.id:baseStorageKey;
 if(nextKey===key)return;
 persist({...state});let next;
 try{next=JSON.parse(localStorage.getItem(nextKey))}catch{}
 if(!next||!Array.isArray(next.items)||!Array.isArray(next.looks))next=associateGuest&&key===baseStorageKey?JSON.parse(JSON.stringify({...state,avatarRequest:null})):freshState();
 key=nextKey;state=next;selected={...(state.selection||state.preview?.selected||{})};ensureLocalLibrary();persist({...state});render();
}
function applyAccount(data,associateGuest=false){
 const previousId=account.user?.id;
 switchAccountState(data.user,associateGuest);
 account={...data,loaded:true};
 if(previousId&&previousId!==data.user?.id){avatarDraft=null;avatarDraftId=null;fullReference=null;avatarDraftSettings=null;renderSetup()}
 renderQuota();renderAccountCard();renderAvatarLibrary();
 if(account.user&&!avatarDraft&&!portraitReference&&!fullReference&&!document.querySelector('[data-page=onboard]').hidden){if(state.avatar)page('mirror');else if(account.avatars.length)page('me')}
 clearTimeout(accountTimer);
 if(account.user&&account.quota?.reserved>0)accountTimer=setTimeout(()=>refreshAccount().catch(()=>{}),6000);
}
let accountRefreshPromise=null;
async function refreshAccount(){
 if(accountRefreshPromise)return accountRefreshPromise;
 accountRefreshPromise=(async()=>{const sequence=++accountSequence;const data=await api('/api/me');if(sequence===accountSequence)applyAccount(data,true);return data})();
 try{return await accountRefreshPromise}finally{accountRefreshPromise=null}
}
function renderQuota(){
 const box=el('avatar-quota');box.replaceChildren();
 if(!account.loaded){box.append(node('span','正在同步分身库…'));return}
 if(!account.user){box.append(node('div','正在准备当前浏览器的分身库，请稍候。'));return}
 const q=account.quota;box.append(node('div',`已生成 ${q.used} 个 AI 分身 · 不限生成次数`));
 box.append(node('p',q.reserved?'有分身正在生成，成功后自动存入分身库。':'可继续生成新分身，结果会保存到分身库。'));
}
function renderAccountCard(){
 const box=el('account-card');box.replaceChildren();const copy=node('div');
 copy.append(node('strong','无需登录，即可使用'),node('p',account.user?`当前浏览器已生成 ${account.quota.used} 个 AI 分身`:'正在准备分身库…'));box.append(copy);
 el('download-avatar').disabled=!state.avatar;
 el('profile-empty').hidden=Boolean(state.avatar);el('profile-avatar').hidden=!state.avatar;document.querySelector('.profile-stage .badge').hidden=!state.avatar;
}
function libraryEntries(){return [...(account.user?account.avatars.map(item=>({...item,remote:true})):[]),...(state.avatars||[]).map(item=>({...item,remote:false}))]}
function renderAvatarLibrary(){
 if(document.querySelector('[data-page="me"]').hidden)return;
 const entries=libraryEntries();el('avatar-library-count').textContent=entries.length+' 个';
 el('avatar-library').replaceChildren(...entries.map(item=>{
  const card=node('article'),img=node('img');card.dataset.active=String(state.avatarId===item.id);img.src=item.remote?item.image_url:item.image;img.alt=item.kind==='generated'?'AI 分身':'照片分身';card.append(img);
  const info=node('div');info.className='library-info';info.append(node('strong',item.kind==='generated'?'AI 生成分身':'照片分身'),node('small',(item.remote?'浏览器身份关联':'当前设备')+(state.avatarId===item.id?' · 当前使用':'')));
  const build=item.settings?.profile?.build;if(build&&profileConfig){const label=profileConfig.fields.find(f=>f.key==='build').options.find(o=>o.value===build)?.label;if(label)info.append(node('small',label))}
  const actions=node('div');actions.className='library-actions';
  actions.append(button(state.avatarId===item.id?'当前分身':'使用',()=>selectAvatar(item)),button('下载',()=>openImageExport(item.remote?item.image_url:item.image,'我的分身.png',item.kind==='generated'?'avatar':'photo')),button('删除',()=>deleteAvatar(item)));
  info.append(actions);card.append(info);return card;
 }));
 if(!entries.length)el('avatar-library').append(emptyState('保存你的第一个分身',account.user?'生成的分身会自动存入这里，也可以上传已有全身照。':'上传全身照或直接生成你的分身。'));
}
async function selectAvatar(item){
 if(generating||avatarPending){message('请等待当前生成完成后再切换分身。');return}
 try{
  if(item.remote)await personImageData(item.image_url);
  const source=item.remote?item.image_url:item.image;
  if(persist({...state,avatar:source,avatarId:item.id,avatarKind:item.kind,avatarSettings:item.settings,preview:null,tryOnJob:null})){showOriginal=false;renderMirror();renderAvatarLibrary();message('已切换当前分身')}
 }catch(error){message(error.message)}
}
async function deleteAvatar(item){
 if(generating||avatarPending){message('请等待当前生成结束。');return}
 if(!confirm(item.kind==='generated'?'删除这个分身？':'删除这个照片分身？'))return;
 try{
  if(item.remote){const data=await api('/api/avatars/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:item.id})});applyAccount(data)}
  const next={...state,avatars:(state.avatars||[]).filter(x=>x.id!==item.id)};
  if(state.avatarId===item.id)Object.assign(next,{avatar:null,avatarId:null,avatarSettings:null,preview:null,tryOnJob:null});
  if(persist(next)){renderMirror();renderAvatarLibrary();message('分身已移除')}
 }catch(error){message(error.message)}
}
async function personImageData(source){
 if(typeof source!=='string')throw Error('请先选择分身。');
 if(source.startsWith('data:image/'))return source;
 if(!/^\/api\/avatars\/[a-f0-9]{32}\/image$/.test(source))throw Error('分身图片地址无效，请重新选择。');
 const response=await fetch(source);if(!response.ok)throw Error(response.status===401?'请刷新页面后重新选择分身。':'无法读取分身图片。');
 const blob=await response.blob();return await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(blob)});
}
async function saveAvatarBeforeConfirm(){
 if(savingAvatar)return null;savingAvatar=true;el('confirm-avatar').disabled=true;
 try{
  if(avatarKind==='generated'){
   if(!remoteAvatarId(avatarDraftId)||!account.user)throw Error('请刷新分身库，查看已生成的分身。');
   await refreshAccount();return {id:avatarDraftId,source:'/api/avatars/'+avatarDraftId+'/image'};
  }
  if(account.user){
   if(!remoteAvatarId(avatarDraftId)){const data=await api('/api/avatars',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image:avatarDraft})});avatarDraftId=data.avatar_id;applyAccount(data)}
   return {id:avatarDraftId,source:'/api/avatars/'+avatarDraftId+'/image'};
  }
  const id=avatarDraftId||crypto.randomUUID();avatarDraftId=id;
  if(!(state.avatars||[]).some(a=>a.id===id)){if(!persist({...state,avatars:[...(state.avatars||[]),{id,image:avatarDraft,kind:'photo',settings:null,created:Date.now()/1000}]}))return null}
  return {id,source:avatarDraft};
 }catch(error){message(error.message);return null}finally{savingAvatar=false;el('confirm-avatar').disabled=false}
}
el('create-first-avatar').onclick=()=>startSetup();
async function ensureAvatarAccount(){
 try{await refreshAccount()}catch{message('暂时无法读取分身库，请稍后再试。');return false}
 if(!account.user){message('无法建立浏览器身份，请允许本站 Cookie 后刷新页面。');return false}
 return true;
}
async function submitAvatarRequest(payload){
 payload={...payload,provider:chosenModel};
 const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(payload)));
 const signature=Array.from(new Uint8Array(hash),x=>x.toString(16).padStart(2,'0')).join('');
 let pending=state.avatarRequest;
 if(!pending||pending.signature!==signature){pending={signature,request_key:crypto.randomUUID()};if(!persist({...state,avatarRequest:pending}))throw Error('设备未能保存请求状态，请释放空间后重试。')}
 if(pending.task)return pending.task;
 try{
  const task=await api('/api/avatar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...payload,request_key:pending.request_key})});
  if(!persist({...state,avatarRequest:{...pending,task}}))state={...state,avatarRequest:{...pending,task}};
  return task;
 }catch(error){if(error.status)forgetAvatarRequest();throw error}
}
function forgetAvatarRequest(){if(state.avatarRequest){if(!persist({...state,avatarRequest:null}))state={...state,avatarRequest:null}}}

// All exported variants use this compositor; clean images remain inside the app.
async function loadBranding(){
 try{branding=await api('/api/export/config');localStorage.setItem('shiyi-export-branding',JSON.stringify(branding))}catch{try{const saved=JSON.parse(localStorage.getItem('shiyi-export-branding'));if(saved)branding=saved}catch{}}
 return branding;
}
async function brandedCanvas(source,kind){
 const image=await loadImage(source),config=await loadBranding();
 const width=1080,bodyHeight=Math.round(width*image.height/image.width),footer=218;
 const canvas=document.createElement('canvas');canvas.width=width;canvas.height=bodyHeight+footer;
 const ctx=canvas.getContext('2d');ctx.fillStyle='#eeeae5';ctx.fillRect(0,0,width,bodyHeight);ctx.drawImage(image,0,0,width,bodyHeight);
 ctx.fillStyle='#191a1e';ctx.fillRect(0,bodyHeight,width,footer);ctx.fillStyle='#ff793d';ctx.fillRect(0,bodyHeight,width,4);
 ctx.textAlign='left';ctx.fillStyle='#ff884c';ctx.font='38px system-ui';ctx.fillText('✦',40,bodyHeight+77);
 ctx.fillStyle='#fff7f1';ctx.font='bold 38px system-ui';ctx.fillText(config.brand||'AI 私人衣橱',92,bodyHeight+77,700);
 const generated=['avatar','tryon','ai-ootd'].includes(kind);
 ctx.fillStyle='#bdb8b7';ctx.font='23px system-ui';ctx.fillText(generated?'AI 生成 · 形象与穿搭效果仅供参考':kind==='photo'?'我的分身 · 专属穿搭参考':'OOTD · 记录你的每日风格',43,bodyHeight+127,760);
 ctx.fillStyle='#92898a';ctx.font='20px system-ui';ctx.fillText('由 AI 私人衣橱制作',43,bodyHeight+174,740);
 const box=166,x=width-box-30,y=bodyHeight+23;
 if(config.qr_url){
  const qr=await loadImage(config.qr_url);ctx.fillStyle='#fff';ctx.fillRect(x,y,box,box);
  const modules=qr.naturalWidth/6,size=Math.floor((box-4)/modules)*modules;
  ctx.imageSmoothingEnabled=false;ctx.drawImage(qr,x+(box-size)/2,y+(box-size)/2,size,size);ctx.imageSmoothingEnabled=true;
  ctx.textAlign='center';ctx.fillStyle='#d3c8c3';ctx.font='16px system-ui';ctx.fillText('扫码下载 APP',x+box/2,bodyHeight+footer-9);
 }else{
  ctx.strokeStyle='#ffffff25';ctx.lineWidth=2;ctx.strokeRect(x,y,box,box);ctx.textAlign='center';ctx.fillStyle='#ff9d6c';ctx.font='bold 32px system-ui';ctx.fillText('APP',x+box/2,y+70);ctx.fillStyle='#aaa0a0';ctx.font='20px system-ui';ctx.fillText('即将上线',x+box/2,y+110);
 }
 ctx.textAlign='left';return canvas;
}
async function openImageExport(source,filename,kind){
 if(!source){message('暂时没有可以保存的图片。');return}
 try{
  message('正在准备保存图片…');const canvas=await brandedCanvas(source,kind);
  const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));if(!blob)throw Error('图片导出失败，请重试。');
  const file=new File([blob],filename,{type:'image/png'});preparedExport={file,filename};el('export-image').src=canvas.toDataURL('image/png');
  el('export-status').textContent=branding.qr_url?'图片已加入品牌水印与 APP 下载二维码。':'图片已加入品牌水印；下载二维码将在 APP 上架后补充。';
  let shareable=false;try{shareable=Boolean(navigator.share&&navigator.canShare&&navigator.canShare({files:[file]}))}catch{}
  el('share-export').hidden=!shareable;message('');if(!el('export-dialog').open)el('export-dialog').showModal();
 }catch{message('图片暂时无法导出，请刷新页面或稍后重试。')}
}
el('close-export').onclick=()=>el('export-dialog').close();
el('export-dialog').addEventListener('close',()=>{preparedExport=null;el('export-image').removeAttribute('src')});
el('download-export').onclick=()=>{
 if(!preparedExport)return;const url=URL.createObjectURL(preparedExport.file),a=document.createElement('a');a.href=url;a.download=preparedExport.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);el('export-status').textContent='已开始下载，也可长按上图或使用系统分享保存。';
};
el('share-export').onclick=async()=>{if(!preparedExport)return;try{await navigator.share({files:[preparedExport.file],title:'我的穿搭 · AI 私人衣橱'})}catch(error){if(error.name!=='AbortError')el('export-status').textContent='无法打开分享菜单，请下载或长按图片保存。'}};
el('download-avatar-draft').onclick=()=>openImageExport(avatarDraft,'我的分身.png',avatarKind==='generated'?'avatar':'photo');
el('download-avatar').onclick=()=>openImageExport(state.avatar,'我的分身.png',state.avatarKind==='generated'?'avatar':'photo');
el('save-preview').onclick=()=>openImageExport(state.preview?.image,'AI-试穿.png','tryon');
el('download').onclick=async()=>{await paint();const generated=state.preview?.selected&&categories.every(c=>(state.preview.selected[c]||'')===(selected[c]||''));openImageExport(el('poster').toDataURL('image/png'),'OOTD.png',generated?'ai-ootd':'ootd')};
const originalClearAvatar=el('clear-avatar').onclick;
el('clear-avatar').onclick=()=>{const item=libraryEntries().find(x=>x.id===state.avatarId);if(item)deleteAvatar(item);else originalClearAvatar()};
const baseRenderMirror=renderMirror;renderMirror=function(){baseRenderMirror();renderQuota();renderAccountCard();renderAvatarLibrary()};
const basePage=page;page=function(name){basePage(name);if(name==='me')renderAvatarLibrary()};
ensureLocalLibrary();persist({...state});renderQuota();renderAccountCard();
loadBranding();refreshAccount().catch(()=>{account.loaded=true;renderQuota();renderAccountCard()});

// Shared preference; each submitted task captures its own provider.
let chosenModel=localStorage.getItem('shiyi-generation-provider')||'seedream';
if(!['seedream','fal'].includes(chosenModel))chosenModel='seedream';
for(const select of document.querySelectorAll('.generation-model')){
 select.value=chosenModel;
 select.onchange=()=>{
  if(generating||avatarPending){select.value=chosenModel;message('请等待当前任务结束后再切换模型。');return}
  chosenModel=select.value;try{localStorage.setItem('shiyi-generation-provider',chosenModel)}catch{}
  document.querySelectorAll('.generation-model').forEach(x=>x.value=chosenModel);
 };
}
api('/api/avatar/options').then(config=>{
 for(const select of document.querySelectorAll('.generation-model'))for(const option of select.options){
  const item=config.models.find(x=>x.id===option.value);option.disabled=!item?.ready;
  if(!item?.ready)option.textContent+='（暂不可用）';
 }
}).catch(()=>{});
