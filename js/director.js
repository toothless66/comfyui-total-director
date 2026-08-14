/**
 * TotalDirector floating panel for ComfyUI.
 *
 * IMPORTANT: No ES module imports. Everything via window globals
 * to avoid timing issues with comfyAPI shim initialization.
 *
 * Self-healing: MutationObserver + polling + registerExtension hook.
 */
(function () {
  "use strict";
  const TAG = "[TotalDirector]";
  const TD_API = (p) => p;

  /* Lazy getters — resolve at call time, never at parse time */
  function app() { return window.comfyAPI && window.comfyAPI.app && window.comfyAPI.app.app; }
  function api() { return window.comfyAPI && window.comfyAPI.api && window.comfyAPI.api.api; }

  /* ─── CSS ─── */
  var CSS = ':root{--td-bg:#0e0e16;--td-bg2:#16161f;--td-glass:rgba(22,22,31,.82);--td-border:rgba(255,255,255,.07);--td-accent:#34d399;--td-accent2:#818cf8;--td-glow:rgba(52,211,153,.12);--td-text:#e2e2ea;--td-dim:#7c7c95;--td-r:14px;--td-rs:8px;--td-ease:cubic-bezier(.4,0,.2,1)}.td-wrap{position:fixed;top:0;right:0;bottom:0;width:380px;z-index:2147483000;font:13px/1.6 system-ui,-apple-system,sans-serif;display:flex;flex-direction:column;background:var(--td-glass);backdrop-filter:blur(28px) saturate(1.4);-webkit-backdrop-filter:blur(28px) saturate(1.4);border-left:1px solid var(--td-border);box-shadow:-12px 0 40px rgba(0,0,0,.45);color:var(--td-text);transform:translateX(0);transition:transform .4s var(--td-ease),opacity .3s var(--td-ease);opacity:1}.td-wrap.td-hidden{transform:translateX(105%);opacity:0;pointer-events:none}@keyframes td-fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}@keyframes td-pulse{0%,100%{opacity:.4}50%{opacity:1}}@keyframes td-slideIn{from{transform:translateX(30px);opacity:0}to{transform:translateX(0);opacity:1}}@keyframes td-glow{0%,100%{box-shadow:0 0 8px var(--td-glow)}50%{box-shadow:0 0 20px var(--td-glow)}}@keyframes td-barShift{0%{background-position:200% 0}100%{background-position:-200% 0}}@keyframes td-dot{0%,80%,100%{transform:scale(0);opacity:.4}40%{transform:scale(1);opacity:1}}@keyframes td-spin{to{transform:rotate(360deg)}}@keyframes td-toastIn{from{transform:translateX(120%);opacity:0}to{transform:translateX(0);opacity:1}}@keyframes td-toastOut{from{transform:translateX(0);opacity:1}to{transform:translateX(120%);opacity:0}}@keyframes td-shimmer{0%{background-position:-200% 0}100%{background-position:200% 0}}.td-toggle{position:fixed;top:16px;right:16px;z-index:2147483001;padding:9px 18px;border:1px solid var(--td-border);border-radius:var(--td-rs);background:linear-gradient(135deg,#34d399,#22b080);color:#fff;cursor:pointer;font:600 13px/1 system-ui,sans-serif;letter-spacing:.3px;transition:all .25s var(--td-ease);box-shadow:0 2px 12px rgba(52,211,153,.25)}.td-toggle:hover{transform:translateY(-1px);box-shadow:0 4px 20px rgba(52,211,153,.35);background:linear-gradient(135deg,#3ee0a8,#2cc48c)}.td-toggle:active{transform:translateY(0) scale(.97)}.td-head{padding:14px 16px;display:flex;align-items:center;gap:10px;border-bottom:1px solid var(--td-border);background:rgba(255,255,255,.02)}.td-head h1{margin:0;font-size:16px;font-weight:700;flex:1;letter-spacing:-.2px;background:linear-gradient(135deg,#34d399 0%,#818cf8 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}.td-head button{background:none;border:none;color:var(--td-dim);cursor:pointer;font-size:18px;padding:4px 8px;border-radius:var(--td-rs);transition:all .2s var(--td-ease)}.td-head button:hover{background:rgba(255,255,255,.06);color:var(--td-text);transform:scale(1.1)}.td-tabs{display:flex;border-bottom:1px solid var(--td-border);background:rgba(255,255,255,.015);position:relative}.td-tab{flex:1;padding:10px 0;text-align:center;cursor:pointer;color:var(--td-dim);font-size:13px;font-weight:500;transition:all .25s var(--td-ease);position:relative}.td-tab::after{content:"";position:absolute;bottom:-1px;left:50%;width:0;height:2px;background:linear-gradient(90deg,#34d399,#818cf8);border-radius:2px;transition:all .35s var(--td-ease);transform:translateX(-50%)}.td-tab:hover{color:var(--td-text);background:rgba(255,255,255,.02)}.td-tab.td-on{color:var(--td-accent);background:rgba(52,211,153,.04)}.td-tab.td-on::after{width:60%}.td-body{flex:1;overflow-y:auto;padding:14px 16px;scrollbar-width:thin;scrollbar-color:rgba(255,255,255,.1) transparent}.td-body::-webkit-scrollbar{width:5px}.td-body::-webkit-scrollbar-track{background:transparent}.td-body::-webkit-scrollbar-thumb{background:rgba(255,255,255,.1);border-radius:4px}.td-body::-webkit-scrollbar-thumb:hover{background:rgba(255,255,255,.18)}.td-block{margin-bottom:14px;animation:td-fadeIn .35s var(--td-ease) both}.td-block:nth-child(2){animation-delay:.05s}.td-block:nth-child(3){animation-delay:.1s}.td-block:nth-child(4){animation-delay:.15s}.td-block label{display:block;font-size:11px;color:var(--td-dim);margin-bottom:5px;text-transform:uppercase;letter-spacing:.6px;font-weight:600}.td-input,.td-textarea{width:100%;box-sizing:border-box;background:rgba(0,0,0,.25);border:1px solid var(--td-border);border-radius:var(--td-rs);color:var(--td-text);padding:9px 12px;font:13px/1.6 system-ui,sans-serif;transition:all .25s var(--td-ease)}.td-textarea{min-height:130px;resize:vertical;line-height:1.7}.td-input:focus,.td-textarea:focus{outline:none;border-color:var(--td-accent);box-shadow:0 0 0 3px var(--td-glow)}.td-input::placeholder,.td-textarea::placeholder{color:var(--td-dim);opacity:.6}.td-btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:9px 18px;border:none;border-radius:var(--td-rs);cursor:pointer;font:600 13px/1 system-ui,sans-serif;color:#fff;transition:all .25s var(--td-ease);position:relative;overflow:hidden;letter-spacing:.3px}.td-btn::after{content:"";position:absolute;inset:0;background:radial-gradient(circle at var(--x,50%) var(--y,50%),rgba(255,255,255,.15),transparent 60%);opacity:0;transition:opacity .3s}.td-btn:hover::after{opacity:1}.td-btn:hover{transform:translateY(-1px);box-shadow:0 4px 16px rgba(0,0,0,.3)}.td-btn:active{transform:translateY(0) scale(.97);box-shadow:none}.td-btn:disabled{opacity:.45;cursor:not-allowed;transform:none!important;box-shadow:none!important}.td-btn:not(.td-sec){background:linear-gradient(135deg,#34d399,#22b080);box-shadow:0 2px 10px rgba(52,211,153,.2)}.td-btn:not(.td-sec):hover{background:linear-gradient(135deg,#3ee0a8,#2cc48c);box-shadow:0 4px 20px rgba(52,211,153,.3)}.td-btn.td-sec{background:rgba(255,255,255,.06);color:var(--td-text);border:1px solid var(--td-border)}.td-btn.td-sec:hover{background:rgba(255,255,255,.1);border-color:rgba(255,255,255,.12)}.td-row{display:flex;gap:8px;margin-bottom:8px}.td-row .td-btn{flex:1}.td-status{margin-top:8px;padding:8px 12px;border-radius:var(--td-rs);font-size:12px;animation:td-slideIn .3s var(--td-ease) both}.td-status.td-running{background:rgba(52,211,153,.08);color:#34d399;border:1px solid rgba(52,211,153,.15)}.td-status.td-ok{background:rgba(99,102,241,.08);color:#818cf8;border:1px solid rgba(99,102,241,.15)}.td-status.td-err{background:rgba(239,68,68,.08);color:#f87171;border:1px solid rgba(239,68,68,.15)}.td-status.td-done{background:rgba(251,191,36,.08);color:#fbbf24;border:1px solid rgba(251,191,36,.15)}.td-progress{height:3px;background:rgba(255,255,255,.06);border-radius:3px;margin-top:6px;overflow:hidden}.td-progress .td-bar{height:100%;border-radius:3px;background:linear-gradient(90deg,#34d399,#818cf8,#34d399);background-size:200% 100%;animation:td-barShift 2.5s linear infinite;transition:width .4s var(--td-ease)}.td-kv{font-size:12px;padding:6px 0;border-bottom:1px solid var(--td-border);display:flex;gap:8px;animation:td-fadeIn .3s var(--td-ease) both}.td-kv:last-child{border-bottom:none}.td-kv .td-k{color:var(--td-dim);min-width:70px;flex-shrink:0}.td-kv .td-v{color:var(--td-text);word-break:break-all}.td-plan{white-space:pre-wrap;font-size:12px;line-height:1.7;color:var(--td-text);padding:10px 12px;background:rgba(0,0,0,.2);border-radius:var(--td-rs);border:1px solid var(--td-border)}.td-tags{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}.td-tag{display:inline-block;padding:3px 10px;border-radius:999px;font-size:11px;font-weight:600;color:#34d399;background:rgba(52,211,153,.08);border:1px solid rgba(52,211,153,.2);animation:td-fadeIn .3s var(--td-ease) both}.td-design{margin-bottom:10px;padding:9px 11px;background:linear-gradient(135deg,rgba(52,211,153,.06),rgba(129,140,248,.06));border:1px solid rgba(129,140,248,.18);border-radius:var(--td-rs);animation:td-fadeIn .35s var(--td-ease) both}.td-design-head{display:flex;align-items:center;gap:6px;font-size:11px;font-weight:700;letter-spacing:.6px;color:#818cf8;margin-bottom:5px;text-transform:uppercase}.td-design-ico{font-size:13px}.td-design-body{font-size:12px;line-height:1.7;color:var(--td-text)}.td-scenes{margin-bottom:10px;display:flex;flex-direction:column;gap:8px;animation:td-fadeIn .35s var(--td-ease) both}.td-scenes-head{display:flex;align-items:center;gap:6px;font-size:11px;font-weight:700;letter-spacing:.6px;color:#34d399;margin-bottom:2px}.td-scenes-ico{font-size:10px}.td-scene{background:rgba(0,0,0,.22);border:1px solid var(--td-border);border-radius:var(--td-rs);padding:8px 10px;transition:all .25s var(--td-ease)}.td-scene:hover{border-color:rgba(52,211,153,.35);background:rgba(52,211,153,.04)}.td-scene-title{font-size:12px;font-weight:600;color:var(--td-text);margin-bottom:2px}.td-scene-meta{font-size:11px;color:var(--td-dim);margin-bottom:3px}.td-scene-summary{font-size:11px;color:var(--td-dim);line-height:1.5;margin-bottom:6px;word-break:break-all}.td-scene-btn{padding:5px 10px;font-size:12px}.td-file{font-size:12px;color:var(--td-dim);margin-top:6px;padding:6px 10px;background:rgba(0,0,0,.15);border-radius:var(--td-rs);border:1px dashed var(--td-border);transition:all .25s var(--td-ease)}.td-file:hover{border-color:var(--td-accent);background:var(--td-glow)}.td-video{margin-top:10px;border-radius:var(--td-rs);overflow:hidden;border:1px solid var(--td-border);animation:td-fadeIn .4s var(--td-ease) both}.td-video video{width:100%;display:block;border-radius:var(--td-rs)}.td-vhead{padding:8px 12px;font-size:12px;color:var(--td-dim);display:flex;align-items:center;gap:6px}.td-vhead svg{width:14px;height:14px;fill:var(--td-accent)}td-input[type=file]{padding:8px;cursor:pointer}@media(prefers-reduced-motion:reduce){.td-wrap,.td-tab::after,.td-btn,.td-toggle,.td-status,.td-block,.td-kv,.td-video,.td-progress .td-bar{animation:none!important;transition-duration:0s!important}}';

  function injectStyle() {
    if (document.getElementById("td-style")) return;
    var s = document.createElement("style");
    s.id = "td-style";
    s.textContent = CSS;
    document.head.appendChild(s);
    console.info(TAG, "CSS injected");
  }

  function h(tag, cls, html) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html !== undefined) n.innerHTML = html;
    return n;
  }

  /* ═══════════════════════════════════════════════════════════════════
   * DirectorPanel — all DOM creation + event handlers
   * ═══════════════════════════════════════════════════════════════════ */
  function DirectorPanel() {
    this.plan = null;
    this.firstFrame = null;
    this.firstFrameB64 = null;
    this.autoRun = true;
    this._build();
  }

  DirectorPanel.prototype._build = function () {
    injectStyle();
    /* Clean stale */
    var oldW = document.getElementById("td-wrap");
    if (oldW) oldW.remove();
    var oldT = document.querySelector('[data-td="toggle"]');
    if (oldT) oldT.remove();

    var wrap = h("div", "td-wrap td-hidden");
    wrap.id = "td-wrap";
    wrap.setAttribute("aria-label", "TotalDirector panel");
    wrap.setAttribute("data-td", "panel");

    var head = h("div", "td-head");
    head.innerHTML = '<h1>\u5bfc\u6f14 Director</h1>';
    var hide = h("button", null, "\u00d7");
    hide.title = "\u9690\u85cf\u9762\u677f";
    var self = this;
    hide.onclick = function () { self.toggle(false); };
    head.appendChild(hide);

    var tabs = h("div", "td-tabs");
    function mkTab(id, label) {
      var t = h("div", "td-tab", label);
      t.dataset.tab = id;
      t.onclick = function () { self._switchTab(id); };
      return t;
    }
    tabs.appendChild(mkTab("create", "\u521b\u4f5c"));
    tabs.appendChild(mkTab("plan", "\u65b9\u6848"));
    tabs.appendChild(mkTab("settings", "\u8bbe\u7f6e"));

    var body = h("div", "td-body");
    this.body = body;
    body.appendChild(this._tabCreate());
    body.appendChild(this._tabPlan());
    body.appendChild(this._tabSettings());
    this._switchTab("create");

    wrap.appendChild(head);
    wrap.appendChild(tabs);
    wrap.appendChild(body);
    document.body.appendChild(wrap);

    self._loadSettings();

    var btn = h("button", "td-toggle", "\u5bfc\u6f14");
    btn.setAttribute("aria-label", "TotalDirector toggle");
    btn.setAttribute("data-td", "toggle");
    btn.onclick = function () { self.toggle(); };
    document.body.appendChild(btn);
    console.info(TAG, "DOM created OK");
  };

  DirectorPanel.prototype._tabCreate = function () {
    var self = this;
    var r = h("div"); r.dataset.tabBody = "create";

    var msg = h("div", "td-block");
    msg.appendChild(h("label", null, "\u9700\u6c42\u63cf\u8ff0 / \u5206\u955c\u811a\u672c"));
    this.input = h("textarea", "td-textarea");
    this.input.placeholder = "\u4f8b:\u4e00\u676130\u79d2\u8d5b\u535a\u670b\u514b\u57ce\u5e02\u591c\u666f\u2026";
    msg.appendChild(this.input);

    var img = h("div", "td-block");
    img.appendChild(h("label", null, "\u9996\u5e27\u53c2\u8003\u56fe (\u53ef\u9009)"));
    this.fileInput = h("input");
    this.fileInput.type = "file";
    this.fileInput.accept = "image/*";
    this.fileInput.className = "td-input";
    this.fileInput.onchange = function () { self._onFile(self.fileInput.files[0]); };
    this.fileName = h("div", "td-file", "\u672a\u9009\u62e9\u56fe\u7247");
    img.appendChild(this.fileInput);
    img.appendChild(this.fileName);

    var st = h("div", "td-status");
    this.status = st;

    var one = h("div", "td-block");
    var bo = h("button", "td-btn td-oneshot", "\u4e00\u952e\u6210\u7247 \u2716\ufe0f \u8ba9\u5bfc\u6f14\u5b8c\u6210\u5168\u90e8");
    bo.title = "\u89c4\u5212\u65b9\u6848 \u2192 \u6784\u5efa\u5de5\u4f5c\u6d41 \u2192 \u81ea\u52a8\u6392\u961f \u2192 \u76d1\u63a7\u8fdb\u5ea6 \u2192 \u56de\u6536\u6210\u7247";
    bo.onclick = function () { self._oneShot(); };
    this.btnOne = bo;
    one.appendChild(bo);

    var runBox = h("div", "td-block");
    runBox.style.display = "none";
    this.runBox = runBox;
    var pg = h("div", "td-progress"); pg.appendChild(h("div"));
    this.progressBar = pg.firstChild;
    this.progressWrap = pg;
    this.runInfo = h("div", "td-runinfo", "");
    runBox.appendChild(pg);
    runBox.appendChild(this.runInfo);
    var vd = h("div", "td-video");
    vd.style.display = "none";
    this.videoBox = vd;
    var vh = h("div", "td-vhead");
    vh.appendChild(h("span", null, "\u6210\u7247"));
    var vdwl = h("a", null, "\u4e0b\u8f7d");
    vdwl.href = "#"; vdwl.target = "_blank";
    this.videoLink = vdwl;
    vh.appendChild(vdwl);
    vd.appendChild(vh);
    var vv = h("video"); vv.controls = true; vv.loop = true;
    this.videoEl = vv;
    vd.appendChild(vv);
    runBox.appendChild(vd);
    r.appendChild(one);
    r.appendChild(runBox);

    var row1 = h("div", "td-row");
    var bp = h("button", "td-btn", "\u751f\u6210\u65b9\u6848");
    bp.onclick = function () { self._plan(); };
    row1.appendChild(bp);

    var row2 = h("div", "td-row");
    var bb = h("button", "td-btn td-sec", "\u6784\u5efa\u5e76\u8f7d\u5165\u753b\u5e03");
    bb.onclick = function () { self._buildWF(false); };
    var br = h("button", "td-btn", "\u6784\u5efa\u5e76\u8fd0\u884c");
    br.onclick = function () { self._buildWF(true); };
    row2.appendChild(bb);
    row2.appendChild(br);
    this.btnBuild = bb;
    this.btnRun = br;
    this.btnPlan = bp;

    var hint = h("div", "td-block");
    hint.innerHTML = '<label>\u8fd0\u884c\u6a21\u5f0f</label><label style="display:flex;align-items:center;gap:6px;color:#e8e8ee"><input type="checkbox" id="td-autorun" checked> \u8f7d\u5165\u540e\u81ea\u52a8\u6392\u961f</label>';
    this.autoRunBox = hint.querySelector("#td-autorun");
    this.autoRunBox.onchange = function () { self.autoRun = self.autoRunBox.checked; };

    r.appendChild(msg);
    r.appendChild(img);
    r.appendChild(st);
    r.appendChild(row1);
    r.appendChild(row2);
    r.appendChild(hint);
    return r;
  };

  DirectorPanel.prototype._tabPlan = function () {
    var self = this;
    var r = h("div"); r.dataset.tabBody = "plan"; r.style.display = "none";
    this.planBox = h("div", "td-plan");
    this.planTitle = h("h2", null, "\u65b9\u6848");
    this.planTags = h("div", "td-tags");
    this.planDesign = h("div", "td-design");
    this.planScenes = h("div", "td-scenes");
    this.planKv = h("dl", "td-kv");
    this.planMp = h("div", "td-mp");
    this.planBox.appendChild(this.planTitle);
    this.planBox.appendChild(this.planTags);
    this.planBox.appendChild(this.planDesign);
    this.planBox.appendChild(this.planScenes);
    this.planBox.appendChild(this.planKv);
    this.planBox.appendChild(this.planMp);

    var ref = h("div", "td-block");
    ref.appendChild(h("label", null, "\u8c03\u6574\u6307\u4ee4"));
    this.refineInput = h("input", "td-input");
    this.refineInput.placeholder = "\u4f8b:\u6539\u4e3a\u6a2a\u5c4f,\u65f6\u957f\u62c9\u52308\u79d2";
    var row = h("div", "td-row");
    var br = h("button", "td-btn", "\u8c03\u6574\u65b9\u6848");
    br.onclick = function () { self._refine(); };
    row.appendChild(br);
    ref.appendChild(this.refineInput);
    ref.appendChild(row);
    r.appendChild(this.planBox);
    r.appendChild(ref);
    return r;
  };

  DirectorPanel.prototype._tabSettings = function () {
    var self = this;
    var r = h("div"); r.dataset.tabBody = "settings"; r.style.display = "none";
    var st = h("div", "td-status"); this.setStatus = st;
    var fields = [
      ["llm","provider","provider (ollama/api)"],["llm","ollama_host","Ollama \u5730\u5740"],
      ["llm","ollama_model","Ollama \u6a21\u578b"],["llm","api_base","API Base"],
      ["llm","api_key","API Key"],["llm","api_model","API \u6a21\u578b"],
      ["llm","roles_mode","\u534f\u8c03\u6a21\u5f0f (single/dual)"],
      ["llm","stage_a_model","\u89d2\u8272A \u68b3\u7406\u53c2\u6570 (dual)"],
      ["llm","stage_b_model","\u89d2\u8272B \u5199\u63d0\u793a\u8bcd (dual)"],
      ["llm","stage_c_model","\u89d2\u8272C \u6267\u884c\u7ec8\u5ba1 (dual)"],
      ["build","default_aspect","\u9ed8\u8ba4\u753b\u5e45 (16:9)"],
      ["build","default_megapixels","\u9ed8\u8ba4\u5206\u8fa8\u7387 MP (0.4)"],
      ["build","max_duration_s","\u6700\u5927\u65f6\u957f (\u79d2)"],
      ["build","sampler","\u91c7\u6837\u5668"],["build","steps","\u6b65\u6570"]
    ];
    this.cfgInputs = {};
    for (var fi = 0; fi < fields.length; fi++) {
      var g = fields[fi][0], k = fields[fi][1], lbl = fields[fi][2];
      var b = h("div", "td-block");
      b.appendChild(h("label", null, lbl));
      var inp = h("input", "td-input"); inp.value = "";
      this.cfgInputs[g + "." + k] = inp;
      b.appendChild(inp);
      r.appendChild(b);
    }
    var row = h("div", "td-row");
    var bs = h("button", "td-btn", "\u4fdd\u5b58\u8bbe\u7f6e");
    bs.onclick = function () { self._saveSettings(); };
    var bl = h("button", "td-btn td-sec", "\u91cd\u65b0\u8f7d\u5165");
    bl.onclick = function () { self._loadSettings(); };
    row.appendChild(bl);
    row.appendChild(bs);
    r.appendChild(row);
    r.appendChild(st);
    return r;
  };

  /* ── Toggle ── */
  DirectorPanel.prototype.toggle = function (force) {
    var w = document.getElementById("td-wrap");
    if (!w) return;
    var show = force !== undefined ? force : w.classList.contains("td-hidden");
    w.classList.toggle("td-hidden", !show);
  };

  /* ── Tab switch ── */
  DirectorPanel.prototype._switchTab = function (id) {
    var tabs = document.querySelectorAll(".td-tab");
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].classList.toggle("td-on", tabs[i].dataset.tab === id);
    }
    var bodies = document.querySelectorAll("[data-tab-body]");
    for (var j = 0; j < bodies.length; j++) {
      bodies[j].style.display = bodies[j].dataset.tabBody === id ? "" : "none";
    }
  };

  /* ── Status ── */
  DirectorPanel.prototype._setStatus = function (text, kind) {
    var el = this.status;
    if (!text) { el.style.display = "none"; return; }
    el.textContent = text;
    el.className = "td-status " + (kind === "ok" ? "td-ok" : kind === "err" ? "td-err" : "td-running");
    el.style.display = "block";
  };

  /* ── HTTP ── */
  DirectorPanel.prototype._post = function (path, payload) {
    return api().fetchApi(TD_API(path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok || !data.ok) throw new Error(data.error || "Failed (" + res.status + ")");
        return data;
      });
    });
  };

  DirectorPanel.prototype._get = function (path) {
    return api().fetchApi(TD_API(path)).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok || !data.ok) throw new Error(data.error || "Failed (" + res.status + ")");
        return data;
      });
    });
  };

  /* ── File upload ── */
  DirectorPanel.prototype._onFile = function (file) {
    if (!file) return;
    this.fileName.innerHTML = "<span>" + file.name + "</span>";
    var self = this;
    var reader = new FileReader();
    reader.onload = function () { self.firstFrameB64 = String(reader.result).split(",")[1]; };
    reader.readAsDataURL(file);
    var fd = new FormData();
    fd.append("image", file);
    fd.append("type", "input");
    fd.append("subfolder", "director");
    fd.append("overwrite", "true");
    api().fetchApi("/upload/image", { method: "POST", body: fd }).then(function (res) {
      return res.json();
    }).then(function (info) {
      self.firstFrame = info;
      self.fileName.innerHTML = "<span>" + (info.subfolder ? info.subfolder + "/" : "") + info.name + "</span>";
    }).catch(function (e) {
      self._setStatus("\u9996\u5e27\u4e0a\u4f20\u5931\u8d25: " + e.message, "err");
    });
  };

  /* ── One-shot: plan -> build -> queue -> monitor -> preview ── */
  DirectorPanel.prototype._oneShot = function () {
    var msg = this.input.value.trim();
    if (!msg) { this._setStatus("\u8bf7\u5148\u8f93\u5165\u9700\u6c42\u6216\u5206\u955c\u811a\u672c", "err"); return; }
    var self = this;
    this._busy(true, this.btnOne);
    this.runBox.style.display = "block";
    this.videoBox.style.display = "none";
    this._setProgress(0);
    this._setRun("\u2460 \u89c4\u5212\u65b9\u6848\u2026");
    this._setStatus("\u4e00\u952e\u6210\u7247\u4e2d\u2026", "running");

    this._post("/director/plan", { message: msg, image_base64: this.firstFrameB64 }).then(function (d) {
      self.plan = d.plan;
      self._renderPlan(d.preview);
      return self._buildAndQueue(d.plan);
    }).then(function (promptId) {
      self._setRun("\u2462 \u5df2\u52a0\u5165\u961f\u5217, \u5f00\u59cb\u76d1\u63a7\u2026");
      return self._monitor(promptId);
    }).then(function (files) {
      self._renderVideo(files);
    }).catch(function (e) {
      self._setStatus("\u4e00\u952e\u6210\u7247\u5931\u8d25: " + e.message, "err");
      self._setRun("\u2716 " + e.message);
    }).finally(function () {
      self._busy(false, self.btnOne);
    });
  };

  DirectorPanel.prototype._buildAndQueue = function (plan) {
    var self = this;
    this._setRun("\u2461 \u6784\u5efa\u5de5\u4f5c\u6d41\u2026");
    var payload = { plan: plan, name: "Director_" + plan.pipeline };
    if (this.firstFrame) {
      payload.first_frame_image = (this.firstFrame.subfolder ? this.firstFrame.subfolder + "/" : "") + this.firstFrame.name;
    }
    return this._post("/director/build", payload).then(function (d) {
      var wf = typeof d.workflow === "string" ? JSON.parse(d.workflow) : d.workflow;
      return app().loadGraphData(wf).then(function () {
        self._setRun("\u2461 \u5df2\u8f7d\u5165\u5de5\u4f5c\u6d41, \u6392\u961f\u2026");
        return app().graphToPrompt().then(function (p) {
          return api().queuePrompt(0, p);
        });
      });
    }).then(function (q) {
      var pid = q && q.prompt_id;
      if (!pid) throw new Error("\u672a\u8fd4\u56de prompt_id");
      return pid;
    });
  };

  DirectorPanel.prototype._buildScene = function (index) {
    var self = this;
    if (!this.plan) return;
    this._busy(true, this.btnOne);
    this.runBox.style.display = "block";
    this.videoBox.style.display = "none";
    this._setProgress(0);
    var scene = (this.plan.scenes || [])[index];
    this._setRun("\u2461 \u6784\u5efa\u573a\u666f #" + (index + 1) + " " + (scene ? scene.title_cn : "") + "\u2026");
    this._setStatus("\u573a\u666f\u6784\u5efa\u4e2d\u2026", "running");

    var payload = { plan: this.plan, scene_index: index, name: "Director_scene_" + (index + 1) };
    if (this.firstFrame) {
      payload.first_frame_image = (this.firstFrame.subfolder ? this.firstFrame.subfolder + "/" : "") + this.firstFrame.name;
    }
    this._post("/director/build", payload).then(function (d) {
      var wf = typeof d.workflow === "string" ? JSON.parse(d.workflow) : d.workflow;
      return app().loadGraphData(wf).then(function () {
        self._setRun("\u2461 \u573a\u666f\u5de5\u4f5c\u6d41\u5df2\u8f7d\u5165, \u6392\u961f\u2026");
        return app().graphToPrompt().then(function (p) {
          return api().queuePrompt(0, p);
        });
      });
    }).then(function (q) {
      var pid = q && q.prompt_id;
      if (!pid) throw new Error("\u672a\u8fd4\u56de prompt_id");
      self._setRun("\u2462 \u573a\u666f\u5df2\u52a0\u5165\u961f\u5217, \u76d1\u63a7\u4e2d\u2026");
      return self._monitor(pid);
    }).then(function (files) {
      self._renderVideo(files);
    }).catch(function (e) {
      self._setStatus("\u573a\u666f\u6784\u5efa\u5931\u8d25: " + e.message, "err");
      self._setRun("\u2716 " + e.message);
    }).finally(function () {
      self._busy(false, self.btnOne);
    });
  };

  DirectorPanel.prototype._monitor = function (promptId) {
    var self = this;
    return new Promise(function (resolve, reject) {
      var a = api();
      var settled = false;
      var pollTimer = null;
      var capTimer = null;

      function finish(err, files) {
        if (settled) return;
        settled = true;
        cleanup();
        if (err) reject(err);
        else resolve(files);
      }
      function cleanup() {
        if (a && typeof a.removeEventListener === "function") {
          a.removeEventListener("progress", onProgress);
          a.removeEventListener("executing", onExecuting);
          a.removeEventListener("execution_success", onSuccess);
          a.removeEventListener("execution_error", onError);
        }
        if (pollTimer) clearInterval(pollTimer);
        if (capTimer) clearTimeout(capTimer);
      }
      function onProgress(ev) {
        var d = ev.detail || {};
        if (typeof d.value === "number" && typeof d.max === "number" && d.max > 0) {
          self._setProgress(Math.round(d.value / d.max * 100));
        }
      }
      function onExecuting(ev) {
        var n = ev.detail;
        self._setRun("\u2462 \u6267\u884c\u4e2d\u2026 \u8282\u70b9 " + (n == null ? "\u2026" : n));
      }
      function onSuccess() {
        self._setProgress(100);
        self._setRun("\u2463 \u6267\u884c\u5b8c\u6210, \u56de\u6536\u6210\u7247\u2026");
        check();
      }
      function onError(ev) {
        var d = ev.detail || {};
        var msg = d.exception_message || d.exception_type || "\u672a\u77e5\u9519\u8bef";
        var node = d.node_type ? " [" + d.node_type + "]" : "";
        finish(new Error(msg + node));
      }
      function check() {
        self._fetchResult(promptId).then(function (r) {
          if (!r.found) return;
          if (r.status === "error") finish(new Error("\u6267\u884c\u5931\u8d25"));
          else if (r.files && r.files.length) finish(null, r.files);
          else if (r.status === "success") finish(new Error("\u672a\u627e\u5230\u6210\u7247\u6587\u4ef6"));
        }, function () { /* transient, keep polling */ });
      }

      if (a && typeof a.addEventListener === "function") {
        a.addEventListener("progress", onProgress);
        a.addEventListener("executing", onExecuting);
        a.addEventListener("execution_success", onSuccess);
        a.addEventListener("execution_error", onError);
      }
      pollTimer = setInterval(check, 5000);
      check();
      capTimer = setTimeout(function () {
        check();
        self._fetchResult(promptId).then(
          function (r) { if (r.found && r.files.length) finish(null, r.files); else finish(new Error("\u76d1\u63a7\u8d85\u65f6 (30\u5206)")); },
          function () { finish(new Error("\u76d1\u63a7\u8d85\u65f6 (30\u5206)")); }
        );
      }, 1800000);
    });
  };

  DirectorPanel.prototype._fetchResult = function (promptId) {
    return this._get("/director/result/" + encodeURIComponent(promptId)).then(function (d) {
      return { found: !!d.found, status: d.status, files: d.found ? (d.files || []) : [] };
    });
  };

  DirectorPanel.prototype._renderVideo = function (files) {
    var self = this;
    var vid = null;
    for (var i = 0; i < (files || []).length; i++) {
      var f = files[i];
      if (/\.[a-zA-Z0-9]+$/.test(f.filename) && !/\.(png|jpe?g|webp)$/i.test(f.filename)) { vid = f; break; }
    }
    if (!vid) vid = (files || [])[0];
    if (!vid) {
      this._setStatus("\u672a\u627e\u5230\u6210\u7247\u6587\u4ef6", "err");
      this._setRun("\u2716 \u672a\u627e\u5230\u6210\u7247\u6587\u4ef6");
      return;
    }
    this.videoEl.src = vid.url;
    this.videoEl.load();
    this.videoLink.href = vid.url;
    this.videoBox.style.display = "block";
    this._setProgress(100);
    this.progressWrap.className = "td-progress td-done";
    this._setRun("\u2713 \u6210\u7247\u5df2\u751f\u6210: " + vid.filename);
    this._setStatus("\u6210\u7247\u5df2\u751f\u6210 \u2713", "ok");
  };

  DirectorPanel.prototype._setProgress = function (pct) {
    this.progressBar.style.width = pct + "%";
  };

  DirectorPanel.prototype._setRun = function (text) {
    this.runInfo.textContent = text;
  };

  /* ── Plan ── */
  DirectorPanel.prototype._plan = function () {
    var msg = this.input.value.trim();
    if (!msg) { this._setStatus("\u8bf7\u5148\u8f93\u5165\u9700\u6c42\u6216\u5206\u955c\u811a\u672c", "err"); return; }
    var self = this;
    this._busy(true, this.btnPlan);
    this._setStatus("\u89c4\u5212\u4e2d\u2026", "running");
    this._post("/director/plan", { message: msg, image_base64: this.firstFrameB64 }).then(function (d) {
      self.plan = d.plan;
      self._renderPlan(d.preview);
      var m = d.model || {};
      var label = m.provider + "/" + m.model;
      if (m.roles) label = "\u534f\u8c03A:" + m.roles.stage_a + " \u2192 B:" + m.roles.stage_b + " \u2192 C:" + m.roles.stage_c;
      self._setStatus("\u65b9\u6848\u5df2\u751f\u6210 (" + label + ")", "ok");
      self._switchTab("plan");
    }).catch(function (e) {
      self._setStatus("\u89c4\u5212\u5931\u8d25: " + e.message, "err");
    }).finally(function () {
      self._busy(false, self.btnPlan);
    });
  };

  /* ── Refine ── */
  DirectorPanel.prototype._refine = function () {
    var inst = this.refineInput.value.trim();
    if (!this.plan) { this._setStatus("\u8bf7\u5148\u751f\u6210\u65b9\u6848", "err"); return; }
    if (!inst) { this._setStatus("\u8bf7\u8f93\u5165\u8c03\u6574\u6307\u4ee4", "err"); return; }
    var self = this;
    this._setStatus("\u8c03\u6574\u4e2d\u2026", "running");
    this._post("/director/refine", { plan: this.plan, instruction: inst }).then(function (d) {
      self.plan = d.plan;
      self._renderPlan(d.preview);
      self._setStatus("\u65b9\u6848\u5df2\u8c03\u6574", "ok");
    }).catch(function (e) {
      self._setStatus("\u8c03\u6574\u5931\u8d25: " + e.message, "err");
    });
  };

  /* ── Render plan ── */
  DirectorPanel.prototype._renderPlan = function (p) {
    this.planTitle.textContent = "\u65b9\u6848 \u00b7 " + p.pipeline;
    /* mood tags */
    this.planTags.innerHTML = "";
    var tags = String(p.mood_tags_cn || "").split(/[,，]/).map(function (s) { return s.trim(); }).filter(Boolean);
    if (!tags.length) tags = [p.pipeline];
    for (var t = 0; t < tags.length; t++) {
      this.planTags.appendChild(h("span", "td-tag", tags[t]));
    }
    /* creative direction card */
    this.planDesign.innerHTML = "";
    var dHead = h("div", "td-design-head");
    dHead.appendChild(h("span", "td-design-ico", "\u2736"));
    dHead.appendChild(h("span", null, "\u8bbe\u8ba1\u7406\u5ff5"));
    this.planDesign.appendChild(dHead);
    var dBody = h("div", "td-design-body", String(p.design_cn || "\u2014"));
    this.planDesign.appendChild(dBody);
    this.planDesign.style.display = p.design_cn ? "" : "none";
    /* multi-scene list */
    this.planScenes.innerHTML = "";
    var scenes = p.scenes || [];
    if (scenes.length) {
      var sh = h("div", "td-scenes-head");
      sh.appendChild(h("span", "td-scenes-ico", "\u25a0"));
      sh.appendChild(h("span", null, "\u5206\u955c\u573a\u666f " + scenes.length + " \u4e2a"));
      this.planScenes.appendChild(sh);
      var self = this;
      for (var si = 0; si < scenes.length; si++) {
        (function (sc, i) {
          var card = h("div", "td-scene");
          var t = h("div", "td-scene-title", "#" + sc.id + " " + sc.title_cn);
          var meta = h("div", "td-scene-meta", sc.duration_s + "s \u00b7 " + sc.aspect + " \u00b7 " + sc.width + "\u00d7" + sc.height);
          var sm = h("div", "td-scene-summary", sc.summary_cn || "\u2014");
          var b = h("button", "td-btn td-sec td-scene-btn", "\u6784\u5efa\u5e76\u8fd0\u884c");
          b.onclick = function () { self._buildScene(i); };
          card.appendChild(t);
          card.appendChild(meta);
          card.appendChild(sm);
          card.appendChild(b);
          self.planScenes.appendChild(card);
        })(scenes[si], si);
      }
    }
    this.planKv.innerHTML = "";
    var rows = [
      ["\u65f6\u957f", p.duration_s + "s (" + p.frames + " \u5e27)"],
      ["\u753b\u5e45", p.aspect + " \u00b7 " + p.width + "\u00d7" + p.height],
      ["\u91c7\u6837", p.sampler + " / " + p.steps + " \u6b65"],
      ["\u79cd\u5b50", p.seed],
      ["\u97f3\u9891", p.audio || "\u2014"],
      ["\u6458\u8981", p.summary_cn || "\u2014"],
      ["\u534f\u8c03", (p.roles ? p.roles.stage_a + " \u2192 " + p.roles.stage_b + " \u2192 " + p.roles.stage_c : "\u2014")]
    ];
    for (var i = 0; i < rows.length; i++) {
      this.planKv.appendChild(h("dt", null, rows[i][0]));
      this.planKv.appendChild(h("dd", null, String(rows[i][1])));
    }
    this.planMp.textContent = p.megaprompt_preview + "\u2026";
    this.planBox.style.display = "block";
  };

  /* ── Build ── */
  DirectorPanel.prototype._buildWF = function (andRun) {
    if (!this.plan) { this._setStatus("\u8bf7\u5148\u751f\u6210\u65b9\u6848", "err"); return; }
    var self = this;
    this._busy(true, andRun ? this.btnRun : this.btnBuild);
    this._setStatus("\u6784\u5efa\u5de5\u4f5c\u6d41\u2026", "running");

    var payload = {
      plan: this.plan,
      name: "Director_" + this.plan.pipeline,
    };
    if (this.firstFrame) {
      payload.first_frame_image = (this.firstFrame.subfolder ? this.firstFrame.subfolder + "/" : "") + this.firstFrame.name;
    }

    this._post("/director/build", payload).then(function (d) {
      var wf = typeof d.workflow === "string" ? JSON.parse(d.workflow) : d.workflow;
      return app().loadGraphData(wf).then(function () {
        self._setStatus("\u5df2\u8f7d\u5165\u5de5\u4f5c\u6d41 (" + self.plan.pipeline + ")", "ok");
        if (andRun || self.autoRun) {
          return app().graphToPrompt().then(function (p) {
            return api().queuePrompt(0, p);
          }).then(function () {
            self._setStatus("\u5df2\u52a0\u5165\u961f\u5217", "ok");
          });
        }
      });
    }).catch(function (e) {
      self._setStatus("\u6784\u5efa\u5931\u8d25: " + e.message, "err");
    }).finally(function () {
      self._busy(false, andRun ? self.btnRun : self.btnBuild);
    });
  };

  /* ── Busy state ── */
  DirectorPanel.prototype._busy = function (on, btn) {
    btn.disabled = on;
    if (on) { btn.dataset.old = btn.textContent; btn.textContent = "\u2026"; }
    else if (btn.dataset.old !== undefined) btn.textContent = btn.dataset.old;
  };

  /* ── Settings load/save ── */
  DirectorPanel.prototype._loadSettings = function () {
    var self = this;
    this._get("/director/config").then(function (d) {
      for (var key in self.cfgInputs) {
        var parts = key.split("."), g = parts[0], k = parts[1];
        self.cfgInputs[key].value = d.config[g] && d.config[g][k] !== undefined ? String(d.config[g][k]) : "";
      }
    }).catch(function (e) {
      self.setStatus.textContent = "\u8f7d\u5165\u5931\u8d25: " + e.message;
      self.setStatus.className = "td-status td-err";
      self.setStatus.style.display = "block";
    });
  };

  DirectorPanel.prototype._saveSettings = function () {
    var self = this;
    this.setStatus.textContent = "\u4fdd\u5b58\u4e2d\u2026";
    this.setStatus.className = "td-status td-running";
    this.setStatus.style.display = "block";
    var patch = {};
    for (var key in this.cfgInputs) {
      var parts = key.split("."), g = parts[0], k = parts[1];
      if (!this.cfgInputs[key].value) continue;
      if (!patch[g]) patch[g] = {};
      var v = this.cfgInputs[key].value;
      if (["default_megapixels", "max_duration_s", "steps"].indexOf(k) >= 0) v = Number(v);
      patch[g][k] = v;
    }
    this._post("/director/config", { config: patch }).then(function () {
      self.setStatus.textContent = "\u8bbe\u7f6e\u5df2\u4fdd\u5b58";
      self.setStatus.className = "td-status td-ok";
    }).catch(function (e) {
      self.setStatus.textContent = "\u4fdd\u5b58\u5931\u8d25: " + e.message;
      self.setStatus.className = "td-status td-err";
    });
    self.setStatus.style.display = "block";
  };

  /* ═══════════════════════════════════════════════════════════════════
   * INIT — no ES imports, just window globals
   * ═══════════════════════════════════════════════════════════════════ */
  var _panel = null;
  var _done = false;

  function _ensureDom() {
    if (_done && document.querySelector('[data-td="toggle"]')) return;
    if (!document.body) return;
    try {
      _panel = new DirectorPanel();
      window.DirectorPanel = _panel;
      _done = true;
      console.info(TAG, "panel ready");
    } catch (err) {
      console.error(TAG, "panel init failed:", err);
    }
  }

  function _bindShortcuts() {
    window.addEventListener("keydown", function (e) {
      if (e.altKey && e.key.toLowerCase() === "d" && _panel) _panel.toggle();
    });
  }

  /* ── Run immediately when script is parsed ── */
  console.info(TAG, "script parsed, readyState:", document.readyState);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      _ensureDom();
      _bindShortcuts();
      _startHealing();
    });
  } else {
    _ensureDom();
    _bindShortcuts();
    _startHealing();
  }

  function _startHealing() {
    if (document.body) {
      new MutationObserver(function () {
        if (!document.querySelector('[data-td="toggle"]')) {
          console.info(TAG, "observer: button missing, re-creating");
          _done = false;
          _ensureDom();
        }
      }).observe(document.body, { childList: true, subtree: true });
    }
    var ticks = 0;
    var iv = setInterval(function () {
      ticks++;
      if (ticks > 30) { clearInterval(iv); return; }
      if (!document.querySelector('[data-td="toggle"]')) {
        console.info(TAG, "poll: button missing, re-creating");
        _done = false;
        _ensureDom();
      }
    }, 2000);
    console.info(TAG, "healing active");
  }

  /* ── Try to register with ComfyUI extension system ── */
  function _tryRegister() {
    var a = app();
    if (!a || typeof a.registerExtension !== "function") return false;
    try {
      a.registerExtension({
        name: "comfyui-total-director.panel",
        setup: function () {
          console.info(TAG, "setup() called by ComfyUI");
          _ensureDom();
          _bindShortcuts();
        },
      });
      console.info(TAG, "registerExtension OK");
      return true;
    } catch (err) {
      console.error(TAG, "registerExtension failed:", err);
      return false;
    }
  }

  if (!_tryRegister()) {
    var rv = setInterval(function () {
      if (_tryRegister()) clearInterval(rv);
    }, 500);
    setTimeout(function () { clearInterval(rv); }, 10000);
  }
})();
