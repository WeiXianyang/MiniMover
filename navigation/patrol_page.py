"""地图巡逻控制台（Web 测试页，供 App UI 参考）"""

PATROL_PAGE_HTML = r'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>地图巡逻控制台</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#1a1a2e;color:#eee;font-family:Arial,sans-serif;padding:10px;max-width:920px;margin:0 auto}
h1{font-size:20px;color:#e94560;margin:8px 0 4px}
.desc{background:#16213e;border-left:4px solid #38bdf8;padding:10px 12px;margin:10px 0;font-size:13px;line-height:1.6;text-align:left;color:#ccc}
.desc b{color:#38bdf8}
.sub{font-size:12px;color:#888;margin-bottom:8px}
.toolbar{display:flex;flex-wrap:wrap;gap:6px;justify-content:center;margin:8px 0}
.toolbar button{padding:8px 14px;border:none;border-radius:8px;cursor:pointer;font-size:13px;background:#0f3460;color:#eee}
.toolbar button:disabled{opacity:.5;cursor:wait}
.toolbar button.danger{background:#e94560}
.toolbar button.primary{background:#1a6e3a}
.toolbar button.warn{background:#b45309}
.toolbar button.active{outline:2px solid #38bdf8}
.map-wrap{position:relative;display:inline-block;border:2px solid #333;border-radius:8px;overflow:hidden;max-width:100%}
.map-wrap img{display:block;max-width:100%;cursor:crosshair;touch-action:none}
.marker{position:absolute;width:14px;height:14px;border:2px solid #fff;border-radius:50%;transform:translate(-50%,-50%);pointer-events:none;font-size:10px;line-height:10px;text-align:center;color:#fff}
.marker.route{background:#e94560}
.marker.start{background:#22c55e}
.info{font-size:12px;color:#aaa;margin:6px 0;word-break:break-all}
.panel{background:#16213e;border-radius:8px;padding:8px;margin:8px 0;text-align:left;font-size:12px}
.panel h3{font-size:13px;color:#38bdf8;margin-bottom:4px}
#pointList{max-height:120px;overflow:auto;font-family:monospace}
#statusBox{color:#38bdf8;min-height:18px}
a{color:#38bdf8}
.flow{font-size:12px;color:#aaa;text-align:left;margin:8px 0;padding-left:16px}
.flow li{margin:4px 0}
</style>
</head>
<body>
<h1>🗺️ 地图巡逻控制台</h1>
<p class="sub">与首页遥控可同时打开；巡逻行驶时请勿同时按方向键抢底盘</p>

<div class="desc">
<b>这是什么？</b> 地图设起点和巡逻路径，网页一键启动巡检。<br>
<b>怎么用？</b> ① 启动导航栈（秒回，后台拉起）→ ② 等上方变绿就绪 → ③ 设起点/画路径 → ④ 开始巡逻
</div>

<a href="/">← 返回 FireGuard 控制面板</a>

<div class="info" id="readyInfo">检查导航栈状态...</div>

<div class="toolbar">
<button class="warn" id="btnStartStack" onclick="startStack()">⚡ 启动导航栈</button>
<button class="danger" id="btnStopStack" onclick="stopStack()">⏻ 关闭导航栈</button>
</div>

<div class="toolbar">
<button id="modeRoute" class="active" onclick="setMode('route')">① 画路径点</button>
<button id="modeStart" onclick="setMode('start')">② 设起点</button>
<button onclick="undoPoint()">撤销</button>
<button class="danger" onclick="clearAll()">清空路线</button>
<button onclick="setInitialPose()">应用起点</button>
<button onclick="uploadRoute()">上传路线</button>
<button class="primary" onclick="startPatrol()">▶ 开始巡逻</button>
<button class="danger" onclick="stopPatrol()">■ 停止巡逻</button>
</div>

<ol class="flow">
<li>点「启动导航栈」后应立刻提示「已开始启动」，再等约 15 秒变绿</li>
<li>变绿后再设起点 / 画路径 / 开始巡逻</li>
<li>首页遥控与本页可共存；巡逻过程中不要同时遥控</li>
</ol>

<div class="info" id="coordInfo">加载地图中...</div>
<div class="map-wrap" id="mapWrap"><img id="mapImg" src="/api/nav/map/image" alt="map"></div>
<div class="panel"><h3>路径点 (<span id="ptCount">0</span>)</h3><div id="pointList">（暂无）</div></div>
<div class="panel"><h3>起点</h3><div id="startInfo">(0.00, 0.00) yaw=0°</div></div>
<div class="panel"><h3>状态</h3><div id="statusBox">等待操作...</div></div>

<script>
var API=window.location.origin,mapInfo={width:0,height:0,resolution:0.05,origin:[-10,-21.2,0]},mapW=0,mapH=0;
var points=[],startPose={x:0,y:0,yaw:0},clickMode='route';
var stackBusy=false,pollFast=false,ready=false;

function setStatus(m,ok){
  var el=document.getElementById('statusBox');
  el.textContent=m;
  el.style.color=ok===false?'#e94560':(ok===true?'#22c55e':'#38bdf8');
}
function setMode(m){
  clickMode=m;
  document.getElementById('modeRoute').classList.toggle('active',m==='route');
  document.getElementById('modeStart').classList.toggle('active',m==='start');
}
function screenToMap(cx,cy){
  var img=document.getElementById('mapImg'),r=img.getBoundingClientRect();
  var sx=(cx-r.left)*mapW/r.width,sy=(cy-r.top)*mapH/r.height;
  return{x:sx*mapInfo.resolution+mapInfo.origin[0],y:(mapH-sy)*mapInfo.resolution+mapInfo.origin[1]};
}
function refreshList(){
  document.getElementById('ptCount').textContent=points.length;
  document.getElementById('pointList').innerHTML=points.length?points.map(function(p,i){
    return (i+1)+'. ('+p.x.toFixed(3)+', '+p.y.toFixed(3)+')';
  }).join('<br>'):'（暂无）';
}
function redraw(){
  document.querySelectorAll('.marker').forEach(function(m){m.remove();});
  var w=document.getElementById('mapWrap');
  var px=(startPose.x-mapInfo.origin[0])/mapInfo.resolution;
  var py=mapH-(startPose.y-mapInfo.origin[1])/mapInfo.resolution;
  var m0=document.createElement('div');m0.className='marker start';
  m0.style.left=(px/mapW*100)+'%';m0.style.top=(py/mapH*100)+'%';w.appendChild(m0);
  points.forEach(function(p,i){
    var px2=(p.x-mapInfo.origin[0])/mapInfo.resolution;
    var py2=mapH-(p.y-mapInfo.origin[1])/mapInfo.resolution;
    var mk=document.createElement('div');mk.className='marker route';
    mk.style.left=(px2/mapW*100)+'%';mk.style.top=(py2/mapH*100)+'%';mk.textContent=i+1;w.appendChild(mk);
  });
}
document.getElementById('mapImg').onload=function(){
  mapW=this.naturalWidth;mapH=this.naturalHeight;
  fetch(API+'/api/nav/map').then(function(r){return r.json();}).then(function(j){
    if(j.code===0){mapInfo=j.data;document.getElementById('coordInfo').textContent='地图 '+mapInfo.width+'×'+mapInfo.height+'  resolution='+mapInfo.resolution;redraw();}
  }).catch(function(){});
};
document.getElementById('mapImg').onclick=function(e){
  var m=screenToMap(e.clientX,e.clientY);
  if(clickMode==='start'){
    startPose.x=m.x;startPose.y=m.y;
    document.getElementById('startInfo').textContent='('+m.x.toFixed(3)+', '+m.y.toFixed(3)+')';
  }else{points.push({x:m.x,y:m.y});refreshList();}
  document.getElementById('coordInfo').textContent='map坐标: ('+m.x.toFixed(3)+', '+m.y.toFixed(3)+')';
  redraw();
};
function undoPoint(){points.pop();refreshList();redraw();}
function clearAll(){
  points=[];refreshList();redraw();
  setStatus('正在清空…');
  fetch(API+'/api/nav/patrol/clear',{method:'POST'}).then(function(r){return r.json();}).then(function(j){setStatus(j.msg||'已清空',j.code===0);});
}
function apiPost(u,b){
  return fetch(API+u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})})
    .then(function(r){return r.json().catch(function(){return {code:-1,msg:'HTTP '+r.status};});});
}
function setInitialPose(){
  setStatus('正在提交起点…');
  return apiPost('/api/nav/initial_pose',startPose).then(function(j){setStatus(j.msg,j.code===0);return j;});
}
function uploadRoute(){
  if(points.length<2){setStatus('至少 2 个路径点',false);return Promise.reject();}
  if(!ready){setStatus('导航栈未就绪，请先等上方变绿',false);return Promise.reject();}
  setStatus('正在上传路线…');
  return apiPost('/api/nav/patrol/route',{points:points}).then(function(j){setStatus(j.msg,j.code===0);return j;});
}
function startPatrol(){
  if(!ready){setStatus('导航栈未就绪，请先启动并等待变绿',false);return;}
  setStatus('准备开始巡逻…');
  setInitialPose().then(function(){return uploadRoute();})
    .then(function(){setStatus('正在启动巡逻…');return apiPost('/api/nav/patrol/start');})
    .then(function(j){setStatus(j.msg,j.code===0);})
    .catch(function(){});
}
function stopPatrol(){
  setStatus('正在停止巡逻…');
  apiPost('/api/nav/patrol/stop').then(function(j){setStatus(j.msg,j.code===0);});
}
function startStack(){
  if(stackBusy){setStatus('操作进行中，请稍候',false);return;}
  stackBusy=true;pollFast=true;
  document.getElementById('btnStartStack').disabled=true;
  setStatus('✓ 已收到点击，正在后台启动…',true);
  document.getElementById('readyInfo').innerHTML='⏳ <b>已接受启动</b> — 后台拉起中，约 15 秒';
  document.getElementById('readyInfo').style.color='#fbbf24';
  // 不等待就绪，立刻返回
  apiPost('/api/nav/stack/start',{wait_ready:false}).then(function(j){
    setStatus(j.msg||'已开始启动',j.code===0);
    checkReady();
  }).catch(function(){
    setStatus('启动请求失败',false);
  }).finally(function(){
    setTimeout(function(){stackBusy=false;document.getElementById('btnStartStack').disabled=false;},1500);
  });
}
function stopStack(){
  if(!confirm('确定关闭导航栈？'))return;
  setStatus('✓ 已收到，正在后台关闭…',true);
  pollFast=true;
  apiPost('/api/nav/stack/stop',{}).then(function(j){
    setStatus(j.msg||'正在停止',j.code===0);
    checkReady();
  }).catch(function(){setStatus('停止请求失败',false);});
}
function checkReady(){
  fetch(API+'/api/nav/stack/status').then(function(r){return r.json();}).then(function(j){
    var el=document.getElementById('readyInfo'),d=j.data||{},msg=d.stack_message||d.hint||'';
    ready=!!(d.patrol_ready||d.stack_ready);
    if(ready){
      pollFast=false;
      el.innerHTML='✓ <b>导航栈就绪</b> — 可画路线并巡逻';
      el.style.color='#22c55e';
    }else if(d.starting){
      pollFast=true;
      el.innerHTML='⏳ <b>启动中</b> — '+msg;
      el.style.color='#fbbf24';
    }else if(d.stopping){
      pollFast=true;
      el.innerHTML='⏳ <b>关闭中</b> — '+msg;
      el.style.color='#fbbf24';
    }else if(d.container_running){
      pollFast=false;
      el.innerHTML='✗ <b>未就绪</b> — 再点「启动导航栈」'+(msg?(' · '+msg):'');
      el.style.color='#e94560';
    }else{
      pollFast=false;
      el.innerHTML='✗ <b>容器未启动</b> — 点「启动导航栈」即可';
      el.style.color='#e94560';
    }
  }).catch(function(){});
}
function pollStatus(){
  if(!ready)return;
  fetch(API+'/api/nav/patrol/status').then(function(r){return r.json();}).then(function(j){
    if(j.code!==0||!j.data)return;
    var s=j.data.status;
    if(!s||s==='idle'||s==='ready'||s==='container_stopped')return;
    setStatus(s+(j.data.patrol_active?' [巡逻中]':''));
  }).catch(function(){});
}
function tick(){
  checkReady();
  pollStatus();
  setTimeout(tick, pollFast?1500:5000);
}
refreshList();
tick();
</script></body></html>'''
