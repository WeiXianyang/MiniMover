"""Read-only Flask dashboard for the hospital-guide voice demonstration."""

import json
from pathlib import Path

from flask import jsonify

from voice_assistant.hospital_guide_telemetry import HospitalGuideTelemetry


HOSPITAL_GUIDE_CONSOLE_HTML = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <link rel="icon" href="data:,">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hospital Guide Demo Console</title>
  <style>
    :root { --bg:#08111f; --panel:#102038; --line:#294764; --text:#eaf2ff; --muted:#9ab0ca; --accent:#2ed7d4; --ok:#31cf8d; --warn:#ffc557; --fail:#ff637b; }
    * { box-sizing:border-box; } body { margin:0; min-height:100vh; background:#08111f; color:var(--text); font:14px/1.5 system-ui,"Microsoft YaHei",sans-serif; }
    header { padding:20px max(18px,calc((100vw - 1120px)/2)); border-bottom:1px solid var(--line); background:#0b1729; } h1 { margin:0; font-size:21px; } .subtitle { margin:5px 0 0; color:var(--muted); font-size:13px; }
    main { max-width:1120px; margin:0 auto; padding:18px; display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; } .panel { background:var(--panel); border:1px solid var(--line); border-radius:10px; overflow:hidden; }
    .panel h2 { margin:0; padding:12px 14px; border-bottom:1px solid var(--line); font-size:14px; } .content { padding:5px 14px; } .kv { display:flex; justify-content:space-between; gap:12px; padding:10px 0; border-bottom:1px solid #203a56; } .kv:last-child { border-bottom:0; } .kv span { color:var(--muted); } .value { max-width:62%; text-align:right; overflow-wrap:anywhere; }
    .state { grid-column:span 3; border-left:4px solid var(--warn); padding:12px 14px; background:#312b1c; } .state.arrived { border-left-color:var(--ok); background:#17372d; } .state.failure { border-left-color:var(--fail); background:#3b2029; }
    .map-link { display:inline-block; color:#082126; background:var(--accent); padding:9px 11px; border-radius:6px; font-weight:700; text-decoration:none; } footer { max-width:1120px; margin:0 auto; padding:0 18px 22px; color:var(--muted); font-size:12px; }
    @media (max-width:760px) { main { grid-template-columns:1fr; padding:12px; } .state { grid-column:span 1; } }
  </style>
</head>
<body data-console="hospital-guide">
  <header>
    <h1 id="title"></h1>
    <p class="subtitle" id="subtitle"></p>
  </header>
  <main>
    <section class="state" id="demo-state-box" aria-live="polite"><strong id="demo-state-message"></strong></section>
    <section class="panel"><h2 id="demo-heading"></h2><div class="content">
      <div class="kv"><span id="demo-phase-name"></span><b class="value" id="demo-phase-value"></b></div>
      <div class="kv"><span id="demo-identity-name"></span><b class="value" id="demo-identity-value"></b></div>
      <div class="kv"><span id="recovery-reason-name"></span><b class="value" id="recovery-reason-value"></b></div>
    </div></section>
    <section class="panel"><h2 id="navigation-heading"></h2><div class="content">
      <div class="kv"><span id="nav-action-status-name"></span><b class="value" id="nav-action-status-value"></b></div>
      <div class="kv"><span id="nav-arrival-name"></span><b class="value" id="nav-arrival-value"></b></div>
      <div class="kv"><span id="nav-distance-name"></span><b class="value" id="nav-distance-value"></b></div>
      <div class="kv"><span id="nav-tolerance-name"></span><b class="value" id="nav-tolerance-value"></b></div>
    </div></section>
    <section class="panel"><h2 id="map-heading"></h2><div class="content">
      <div class="kv"><span id="nav-target-name"></span><b class="value" id="nav-target-value"></b></div>
      <div class="kv"><span id="nav-map-pose-name"></span><b class="value" id="nav-map-pose-value"></b></div>
      <div class="kv"><span id="nav-message-name"></span><b class="value" id="nav-message-value"></b></div>
      <p><a class="map-link" href="/nav/patrol" target="_blank" rel="noopener" id="map-link"></a></p>
    </div></section>
  </main>
  <footer id="footer"></footer>
  <script>
    const text = {
      title:"\u4e94\u5206\u949f\u533b\u9662\u5bfc\u8bca\u6f14\u793a", subtitle:"\u53ea\u8bfb\u5c55\u793a\u6f14\u793a\u72b6\u6001\u4e0e Nav2 \u771f\u5b9e\u8bc1\u636e\uff1b\u4e0d\u5c55\u793a\u7167\u7247\u3001\u8bed\u97f3\u539f\u6587\u6216\u8bc6\u522b\u8be6\u60c5\u3002",
      demo:"\u6f14\u793a\u4f1a\u8bdd", phase:"\u9636\u6bb5", identity:"\u6b22\u8fce\u663e\u793a", recovery:"\u6062\u590d\u539f\u56e0", navigation:"Nav2 \u8bc1\u636e", action:"Action \u72b6\u6001", arrival:"\u5230\u8fbe\u5224\u5b9a", distance:"\u7ec8\u70b9\u8ddd\u79bb", tolerance:"\u5bb9\u5dee", map:"\u5730\u56fe\u8bc1\u636e", target:"\u76ee\u6807", pose:"map \u4f4d\u59ff", message:"\u771f\u5b9e\u72b6\u6001\u4fe1\u606f", guest:"\u8bbf\u5ba2", none:"\u65e0", arrived:"\u5df2\u5230\u8fbe\uff08\u53cc\u6761\u4ef6\u5df2\u9a8c\u8bc1\uff09", notArrived:"\u672a\u5230\u8fbe", openMap:"\u6253\u5f00\u53ea\u8bfb\u5730\u56fe\u9762\u677f", unavailable:"\u65e0\u6cd5\u83b7\u53d6\u6f14\u793a\u72b6\u6001", footer:"\u4ec5 navigation.arrived=true \u8868\u793a\u5df2\u5230\u8fbe\uff1bPENDING\u3001ACTIVE\u3001FAILED \u548c CANCELLED \u4fdd\u6301\u4e3a\u5b9e\u9645\u72b6\u6001\u3002"
    };
    const byId = id => document.getElementById(id);
    const set = (id, value) => { byId(id).textContent = value; };
    [["title",text.title],["subtitle",text.subtitle],["demo-heading",text.demo],["demo-phase-name",text.phase],["demo-identity-name",text.identity],["recovery-reason-name",text.recovery],["navigation-heading",text.navigation],["nav-action-status-name",text.action],["nav-arrival-name",text.arrival],["nav-distance-name",text.distance],["nav-tolerance-name",text.tolerance],["map-heading",text.map],["nav-target-name",text.target],["nav-map-pose-name",text.pose],["nav-message-name",text.message],["map-link",text.openMap],["footer",text.footer]].forEach(([id,value]) => set(id,value));
    const number = value => typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : text.none;
    const point = value => value && typeof value.x === "number" && typeof value.y === "number" ? `${number(value.x)}, ${number(value.y)}${typeof value.theta === "number" ? `, ${number(value.theta)}` : ""}` : text.none;
    function render(data) {
      const session = data && data.session || {}; const nav = data && data.navigation || {}; const arrived = nav.arrived === true;
      set("demo-phase-value",session.phase || "READY"); set("demo-identity-value",session.display_name || text.guest); set("recovery-reason-value",session.recovery_reason || text.none);
      set("nav-action-status-value",nav.status || "IDLE"); set("nav-arrival-value",arrived ? text.arrived : text.notArrived); set("nav-distance-value",nav.distance_m === null || nav.distance_m === undefined ? text.none : `${number(nav.distance_m)} m`); set("nav-tolerance-value",nav.tolerance_m === null || nav.tolerance_m === undefined ? text.none : `${number(nav.tolerance_m)} m`);
      set("nav-target-value",point(nav.target)); const pose = nav.pose; set("nav-map-pose-value",pose && pose.valid === true && pose.frame_id === "map" ? `${number(pose.x)}, ${number(pose.y)}` : text.none); set("nav-message-value",nav.message || text.none);
      const box = byId("demo-state-box"); box.className = "state" + (arrived ? " arrived" : (nav.status === "FAILED" || nav.status === "CANCELLED" ? " failure" : "")); set("demo-state-message",arrived ? text.arrived : `${session.phase || "READY"} / ${nav.status || "IDLE"}`);
    }
    async function refresh() { try { const response = await fetch("/api/hospital-guide/demo/status", {cache:"no-store"}); if (!response.ok) throw new Error("status unavailable"); render((await response.json()).data || {}); } catch (_) { render({session:{phase:"RECOVERY",recovery_reason:text.unavailable},navigation:{status:"FAILED",arrived:false,message:text.unavailable}}); } }
    refresh(); window.setInterval(refresh, 1000);
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

    @app.route("/favicon.ico")
    def hospital_guide_favicon():
        return "", 204

    @app.route("/api/hospital-guide/status")
    def hospital_guide_status():
        snapshot = HospitalGuideTelemetry(runtime_path).read()
        snapshot["service_online"] = runtime_path.exists()
        return jsonify({"code": 0, "data": snapshot})

    @app.route("/api/hospital-guide/config")
    def hospital_guide_config():
        return jsonify({"code": 0, "data": _public_department_config(config_path)})
