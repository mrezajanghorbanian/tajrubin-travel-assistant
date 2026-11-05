'use strict';
const $=id=>document.getElementById(id);
let csrf='',busy=false;
const labels={destination:'مقصد',duration:'مدت سفر',dates:'تاریخ',party:'تعداد مسافر',budget:'بودجه',preferences:'ترجیح‌ها'};
function render(data){
  $('messages').replaceChildren();
  for(const item of data.history){const bubble=document.createElement('div');bubble.className='bubble '+item.role;const sender=document.createElement('span');sender.className='sender';sender.textContent=item.role==='user'?'شما':'تجربین';bubble.append(sender,document.createTextNode(item.text));$('messages').append(bubble);}
  $('messages').scrollTop=$('messages').scrollHeight;
  $('examples').hidden=data.history.length>0;
  $('facts').replaceChildren();
  for(const [key,label] of Object.entries(labels)){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=data.state[key]?.value||'هنوز مشخص نیست';$('facts').append(dt,dd);}
  $('turns').textContent=data.turns+' از ۴';
}
async function action(path,payload={}){
  if(busy)return;busy=true;$('error').hidden=true;
  for(const el of document.querySelectorAll('button,textarea'))el.disabled=true;
  const started=Date.now();$('status').textContent='در حال پردازش…';
  const timer=setInterval(()=>{$('status').textContent='در حال پردازش با مدل محلی · '+Math.floor((Date.now()-started)/1000)+' ثانیه';},1000);
  try{const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(payload)});const data=await response.json();if(data.history)render(data);if(!response.ok)throw new Error(data.error||'درخواست انجام نشد.');if(path==='/api/chat')$('message').value='';$('status').textContent='آماده';}
  catch(error){$('error').textContent=error.message||'ارتباط با سرویس محلی قطع شد.';$('error').hidden=false;$('status').textContent='درخواست انجام نشد';}
  finally{clearInterval(timer);busy=false;for(const el of document.querySelectorAll('button,textarea'))el.disabled=false;$('message').focus();}
}
$('chat').addEventListener('submit',event=>{event.preventDefault();const message=$('message').value.trim();if(message.length<3){$('error').textContent='پیام باید دست‌کم سه نویسه داشته باشد.';$('error').hidden=false;return;}action('/api/chat',{message});});
$('confirm').addEventListener('click',()=>action('/api/confirm'));
$('reset').addEventListener('click',()=>action('/api/reset'));
for(const el of document.querySelectorAll('[data-example]'))el.addEventListener('click',()=>{$('message').value=el.dataset.example;$('message').focus();});
(async()=>{try{const r=await fetch('/api/state');const data=await r.json();if(!r.ok)throw new Error(data.error);csrf=data.csrf;render(data);$('status').textContent='آماده';}catch(error){$('error').textContent='جلسه محلی در دسترس نیست؛ صفحه را تازه‌سازی کن.';$('error').hidden=false;$('status').textContent='اتصال برقرار نشد';}})();
