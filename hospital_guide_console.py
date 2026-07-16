"""Read-only Flask dashboard for the hospital-guide voice demonstration."""

import json
from pathlib import Path

from flask import jsonify

from voice_assistant.hospital_guide_telemetry import HospitalGuideTelemetry


HOSPITAL_GUIDE_CONSOLE_HTML = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hospital Guide Console</title>
  <style>
    :root { --bg:#08111f; --panel:#111d31; --line:#283a56; --text:#eaf2ff; --muted:#91a4c4; --cyan:#2ed7d4; --green:#2fcf8c; --amber:#ffc557; --red:#ff637b; }
    * { box-sizing:border-box; } body { margin:0; min-height:100vh; background:radial-gradient(circle at 20% 0%,#15335d 0,#08111f 42%,#060c16 100%); color:var(--text); font:14px/1.5 system-ui,"Microsoft YaHei",sans-serif; }
    header { min-height:70px; display:flex; gap:16px; align-items:center; justify-content:space-between; padding:12px 24px; border-bottom:1px solid var(--line); background:#0b1628e8; position:sticky; top:0; z-index:4; backdrop-filter:blur(10px); }
    h1 { margin:0; font-size:20px; } .subtitle { color:var(--muted); font-size:12px; margin-top:3px; } .chips { display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }
    .chip { border:1px solid #314a6d; border-radius:999px; color:#cbe1ff; padding:5px 10px; font-size:12px; background:#142640; } .chip.ok { color:#05241a; border-color:var(--green); background:var(--green); font-weight:700; } .chip.warn { color:#4f3300; border-color:var(--amber); background:var(--amber); font-weight:700; }
    main { max-width:1560px; margin:0 auto; padding:18px; display:grid; grid-template-columns:minmax(340px,1.35fr) minmax(280px,.88fr) minmax(290px,.95fr); gap:15px; } .panel { background:linear-gradient(160deg,#14233a,#0e192b); border:1px solid var(--line); border-radius:14px; overflow:hidden; box-shadow:0 10px 38px #02071060; }
    .conversation { grid-row:span 2; min-height:610px; } .panel-head { min-height:48px; padding:13px 15px; border-bottom:1px solid var(--line); display:flex; justify-content:space-between; gap:10px; align-items:center; } .panel-head h2 { font-size:14px; margin:0; } .label { font-size:11px; border-radius:999px; padding:3px 7px; color:var(--cyan); background:#163554; white-space:nowrap; }
    .empty { padding:24px 16px; color:var(--muted); text-align:center; } .messages { padding:16px; display:flex; flex-direction:column; gap:12px; } .message { max-width:88%; padding:10px 12px; border-radius:12px; border:1px solid #2a405f; background:#182944; white-space:pre-wrap; word-break:break-word; } .message.user { align-self:flex-end; background:#1d5877; border-color:#317eab; } .message small { display:block; margin-top:5px; color:#bbcae4; font-size:11px; }
    .content { padding:14px; } .state-box { border-left:3px solid var(--amber); padding:10px 11px; border-radius:7px; color:#ffe1a0; background:#382d19; white-space:pre-wrap; } .state-box.idle { color:#b9c8df; background:#182944; border-left-color:#5277a6; } .kv { border-bottom:1px solid #243650; padding:10px 0; display:flex; gap:12px; justify-content:space-between; } .kv:last-child { border:0; } .kv span { color:var(--muted); } .value { text-align:right; max-width:64%; word-break:break-word; }
    .event-list { padding:14px 15px 4px; } .event { border-left:2px solid #35577f; padding:0 0 15px 13px; margin-left:4px; position:relative; } .event:before { content:""; position:absolute; width:8px; height:8px; left:-5px; top:5px; border-radius:50%; background:var(--cyan); } .event strong { display:block; font-size:13px; } .event small { display:block; color:var(--muted); margin-top:3px; }
    .map-card { padding:14px; } .map-preview { height:168px; margin-bottom:12px; border-radius:9px; position:relative; overflow:hidden; background:repeating-linear-gradient(0deg,#17304e 0,#17304e 1px,transparent 1px,transparent 29px),repeating-linear-gradient(90deg,#17304e 0,#17304e 1px,transparent 1px,transparent 29px),#0a172a; } .map-preview:after { content:""; position:absolute; width:45%; height:34%; left:16%; top:25%; border-left:3px solid var(--cyan); border-bottom:3px solid var(--cyan); } .robot { position:absolute; z-index:1; width:20px; height:20px; border-radius:5px; left:16%; top:25%; background:var(--green); box-shadow:0 0 0 5px #2fcf8c36; } .target { position:absolute; z-index:1; width:17px; height:17px; border-radius:50%; left:59%; top:59%; background:var(--amber); box-shadow:0 0 0 5px #ffc55730; }
    a.button { display:inline-block; width:100%; color:#032429; background:var(--cyan); font-weight:700; text-decoration:none; text-align:center; padding:9px; border-radius:8px; } .hint { margin-top:10px; color:var(--muted); font-size:12px; } .departments { padding:0 14px 14px; display:grid; gap:8px; } .department { padding:9px 10px; border-radius:8px; border:1px solid #294361; background:#11243d; display:flex; justify-content:space-between; gap:10px; } .department small { color:var(--muted); } .on { color:var(--green); } .off { color:var(--amber); }
    footer { max-width:1560px; margin:0 auto; padding:0 18px 22px; color:var(--muted); font-size:12px; } @media(max-width:1000px) { main { grid-template-columns:1fr 1fr; } .conversation { grid-row:span 1; grid-column:span 2; min-height:0; } } @media(max-width:680px) { header { align-items:flex-start; flex-direction:column; } .chips { justify-content:flex-start; } main { grid-template-columns:1fr; padding:10px; } .conversation { grid-column:span 1; } }
  </style>
</head>
<body data-console="hospital-guide">
  <header>
    <div><h1 id="title"></h1><div class="subtitle" id="subtitle"></div></div>
    <div class="chips"><span class="chip" id="service-chip"></span><span class="chip" id="gate-chip"></span></div>
  </header>
  <main>
    <section class="panel conversation"><div class="panel-head"><h2 id="conversation-heading"></h2><span class="label" id="memory-label"></span></div><div class="messages" id="messages"></div></section>
    <section class="panel"><div class="panel-head"><h2 id="state-heading"></h2><span class="label" id="state-label"></span></div><div class="content"><div class="state-box idle" id="state-box"></div><div class="kv"><span id="pending-name"></span><b class="value" id="pending-value"></b></div><div class="kv"><span id="evidence-name"></span><b class="value" id="evidence-value"></b></div><div class="kv"><span id="navigation-name"></span><b class="value" id="navigation-value"></b></div></div></section>
    <section class="panel"><div class="panel-head"><h2 id="map-heading"></h2><span class="label" id="map-label"></span></div><div class="map-card"><div class="map-preview"><i class="robot"></i><i class="target"></i></div><div class="kv"><span id="target-name"></span><b class="value" id="target-value"></b></div><a class="button" href="/nav/patrol" target="_blank" rel="noopener" id="map-link"></a><div class="hint" id="map-hint"></div></div></section>
    <section class="panel"><div class="panel-head"><h2 id="event-heading"></h2><span class="label" id="event-label"></span></div><div class="event-list" id="events"></div></section>
    <section class="panel"><div class="panel-head"><h2 id="department-heading"></h2><span class="label" id="department-label"></span></div><div class="departments" id="departments"></div></section>
  </main>
  <footer id="footer"></footer>
  <script>
    const text = { title:"\u533b\u9662\u5bfc\u8bca\u63a7\u5236\u53f0", subtitle:"MiniMover \u00b7 \u7b54\u8fa9\u6f14\u793a\u6a21\u5f0f \u00b7 \u4ec5\u5bfc\u8bca\u4e0e\u4e00\u822c\u5065\u5eb7\u6559\u80b2", online:"\u8bed\u97f3\u670d\u52a1\u5728\u7ebf", offline:"\u8bed\u97f3\u670d\u52a1\u672a\u4e0a\u62a5\u72b6\u6001", gate:"\u5bfc\u822a\u9700\u8bed\u97f3\u660e\u786e\u786e\u8ba4", conversation:"\u5b9e\u65f6\u5bf9\u8bdd", memory:"\u6700\u8fd1\u591a\u8f6e\u8bb0\u5fc6", state:"\u5bfc\u8bca\u72b6\u6001", stateLabel:"\u786e\u8ba4\u95e8\u7981", pending:"\u5f85\u786e\u8ba4\u79d1\u5ba4", none:"\u65e0", evidence:"\u672c\u8f6e\u77e5\u8bc6\u5e93\u547d\u4e2d", navigation:"\u5bfc\u822a\u5ba1\u8ba1", map:"\u5730\u56fe\u76ee\u6807", mapLabel:"\u590d\u7528\u73b0\u6709\u5efa\u6a21", target:"\u5f53\u524d\u76ee\u6807", openMap:"\u6253\u5f00\u5730\u56fe\u9009\u70b9 / \u5de1\u903b\u63a7\u5236\u53f0", mapHint:"\u5750\u6807\u4ec5\u80fd\u6765\u81ea\u5df2\u6709\u5730\u56fe\u9009\u70b9\u914d\u7f6e\uff0cLLM \u65e0\u6cd5\u751f\u6210\u6216\u4fee\u6539\u5750\u6807\u3002", events:"\u6d41\u7a0b\u5ba1\u8ba1", eventsLabel:"\u5b9e\u65f6\u4e8b\u4ef6", departments:"\u79d1\u5ba4\u70b9\u4f4d", departmentsLabel:"\u914d\u7f6e\u4e00\u89c8", noMessages:"\u7b49\u5f85\u8bed\u97f3\u670d\u52a1\u8f93\u5165\u2026", noEvents:"\u6682\u65e0\u6d41\u7a0b\u4e8b\u4ef6\u3002", enabled:"\u5df2\u542f\u7528", disabled:"\u5f85\u9009\u70b9\u542f\u7528", waiting:"\u6b63\u5728\u7b49\u5f85\u60a8\u660e\u786e\u786e\u8ba4\u3002", awake:"\u5bfc\u8bca\u4f1a\u8bdd\u5df2\u5c31\u7eea\u3002", idle:"\u8bed\u97f3\u670d\u52a1\u6682\u672a\u4e0a\u62a5\u4f1a\u8bdd\u3002", footer:"\u672c\u9875\u4ec5\u8bfb\u5c55\u793a\u771f\u5b9e\u8bed\u97f3\u5bfc\u8bca\u72b6\u6001\uff1b\u4e0d\u63d0\u4f9b\u7f51\u9875\u76f4\u63a5\u4e0b\u53d1\u5bfc\u822a\u7684\u5165\u53e3\u3002" };
    const byId = (id) => document.getElementById(id); const set = (id, value) => byId(id).textContent = value;
    [ ["title",text.title],["subtitle",text.subtitle],["conversation-heading",text.conversation],["memory-label",text.memory],["state-heading",text.state],["state-label",text.stateLabel],["pending-name",text.pending],["evidence-name",text.evidence],["navigation-name",text.navigation],["map-heading",text.map],["map-label",text.mapLabel],["target-name",text.target],["map-link",text.openMap],["map-hint",text.mapHint],["event-heading",text.events],["event-label",text.eventsLabel],["department-heading",text.departments],["department-label",text.departmentsLabel],["footer",text.footer] ].forEach(([id,value])=>set(id,value));
    function clear(node) { node.replaceChildren(); } function add(node, tag, value, className) { const child=document.createElement(tag); if(className)child.className=className; child.textContent=value; node.append(child); return child; }
    function formatNavigation(nav) { if (!nav) return text.none; return nav.message || nav.status || text.none; }
    function renderStatus(data) {
      const online=Boolean(data.service_online), session=data.session||{}, pending=session.pending_department, nav=data.navigation||{};
      const service=byId("service-chip"); service.textContent=online?text.online:text.offline; service.className="chip "+(online?"ok":"warn"); set("gate-chip",text.gate);
      const box=byId("state-box"); const waiting=session.state==="WAITING_CONFIRMATION"; box.textContent=waiting?text.waiting:(online?text.awake:text.idle); box.className="state-box "+(waiting?"":"idle");
      set("pending-value",pending ? `${pending.name||pending.id||text.none}${pending.floor?" \u00b7 "+pending.floor:""}` : text.none); set("evidence-value",String((data.knowledge||{}).evidence_count||0)); set("navigation-value",formatNavigation(nav));
      const target=nav.department||pending; set("target-value",target ? `${target.name||target.id||text.none}${target.floor?" \u00b7 "+target.floor:""}` : text.none);
      const messages=byId("messages"); clear(messages); const memory=Array.isArray(data.memory)?data.memory:[]; if(!memory.length){add(messages,"div",text.noMessages,"empty");} memory.slice(-12).forEach(item=>{const message=add(messages,"div",item.content||"",`message ${item.role==="user"?"user":"assistant"}`); add(message,"small",item.role==="user"?"\u8bbf\u5ba2":"\u5bfc\u8bca\u673a\u5668\u4eba");});
      const events=byId("events"); clear(events); const rows=Array.isArray(data.events)?data.events:[]; if(!rows.length){add(events,"div",text.noEvents,"empty");} rows.slice(-10).reverse().forEach(item=>{const row=add(events,"div","","event"); add(row,"strong",item.message||item.type||""); add(row,"small",`${item.type||"reply"}${item.at?" \u00b7 "+item.at:""}`);});
    }
    function renderConfig(data) { const root=byId("departments"); clear(root); const departments=Array.isArray(data.departments)?data.departments:[]; if(!departments.length){add(root,"div",text.none,"empty"); return;} departments.forEach(dept=>{const card=add(root,"div","","department"); const left=add(card,"div",dept.name||dept.id||text.none); add(left,"small",dept.floor||""); const right=add(card,"div",dept.navigation_enabled?text.enabled:text.disabled,dept.navigation_enabled?"on":"off");}); }
    async function refresh() { try { const [status,config]=await Promise.all([fetch("/api/hospital-guide/status",{cache:"no-store"}),fetch("/api/hospital-guide/config",{cache:"no-store"})]); if(status.ok)renderStatus((await status.json()).data||{}); if(config.ok)renderConfig((await config.json()).data||{}); } catch (_) { renderStatus({service_online:false,session:{state:"IDLE"}}); } }
    refresh(); window.setInterval(refresh,1000);
  </script>
</body>
</html>'''


def _public_department_config(config_path):
    fallback = {"hospital_name": "MiniMover \u793a\u8303\u533b\u9662", "departments": []}
    try:
        raw = json.loads(Path(config_path).read_text(encoding="utf-8-sig"))
    except (OSError, TypeError, ValueError):
        return fallback
    if not isinstance(raw, dict):
        return fallback
    departments = []
    for item in raw.get("departments", []):
        if not isinstance(item, dict):
            continue
        navigation = item.get("navigation") if isinstance(item.get("navigation"), dict) else {}
        departments.append({
            "id": str(item.get("id") or "").strip(),
            "name": str(item.get("name") or "").strip(),
            "floor": str(item.get("floor") or "").strip(),
            "navigation_enabled": bool(navigation.get("enabled", False)),
        })
    return {
        "hospital_name": str(raw.get("hospital_name") or fallback["hospital_name"]),
        "departments": departments,
    }


def register_hospital_guide_console(app, runtime_path, config_path):
    """Register display-only routes for the voice guide and its map configuration."""

    runtime_path = Path(runtime_path)
    config_path = Path(config_path)

    @app.route("/hospital-guide")
    def hospital_guide_page():
        return HOSPITAL_GUIDE_CONSOLE_HTML

    @app.route("/api/hospital-guide/status")
    def hospital_guide_status():
        snapshot = HospitalGuideTelemetry(runtime_path).read()
        snapshot["service_online"] = runtime_path.exists()
        return jsonify({"code": 0, "data": snapshot})

    @app.route("/api/hospital-guide/config")
    def hospital_guide_config():
        return jsonify({"code": 0, "data": _public_department_config(config_path)})
