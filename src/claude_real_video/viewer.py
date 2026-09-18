"""--viewer: write viewer.html into the output folder — a single local file
showing the video, the kept keyframes as a browsable grid, and a clickable
transcript: every line carries its timestamp, so clicking one seeks the video
to that moment, and the line under the playhead highlights as it plays. A
"read" toggle drops the timestamps and speaker chips and reflows the lines as
prose, for when you want to read the call rather than scrub it.
No network, no dependencies. (The Pro version adds a clickable synced
perception/shot timeline on top of this.)

The page is built from a template with __TOKEN__ placeholders rather than an
f-string: the JS below is large and brace-heavy, and doubling every brace to
survive f-string interpolation is a standing invitation to a syntax error.
"""
from __future__ import annotations

import glob
import html
import json
import os


def _load_segments(out_dir: str) -> list[dict]:
    """Timestamped transcript lines, if the run produced any.

    transcript.json is written by every path that yields timings (whisper,
    subtitle sidecars, the speaker-split pipeline). `speaker` is optional —
    it only appears once a diarization pass has labelled the lines. Keys are
    short because this list is inlined into the page and a long call runs to
    thousands of segments."""
    p = os.path.join(out_dir, "transcript.json")
    if not os.path.exists(p):
        return []
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    segs = data.get("segments") if isinstance(data, dict) else data
    if not isinstance(segs, list):
        return []
    out: list[dict] = []
    for s in segs:
        try:
            text = str(s.get("text", "")).strip()
            if not text:
                continue
            row = {"t": round(float(s["start"]), 2), "x": text}
            if s.get("speaker"):
                row["s"] = str(s["speaker"])
            out.append(row)
        except (KeyError, TypeError, ValueError):
            continue
    return out


def write_viewer(out_dir: str, video_path: str | None) -> str:
    frames = sorted(glob.glob(os.path.join(out_dir, "frames", "*.jpg")))
    # frames.json (issue #7): per-frame source timestamps — shown on each cell,
    # and the lightbox gets a "play from here" jump when the video is present.
    ts: dict[str, float] = {}
    ts_label: dict[str, str] = {}
    fj = os.path.join(out_dir, "frames.json")
    if os.path.exists(fj):
        try:
            for fr in json.load(open(fj, encoding="utf-8")).get("frames", []):
                ts[fr["file"]] = float(fr["timestamp_sec"])
                ts_label[fr["file"]] = str(fr.get("timestamp", ""))[3:11]  # MM:SS.mmm
        except Exception:
            ts, ts_label = {}, {}

    segments = _load_segments(out_dir)
    transcript = ""
    tpath = os.path.join(out_dir, "transcript.txt")
    if os.path.exists(tpath):
        # explicit utf-8: the transcript/HTML carry CJK and would crash on
        # Windows' default cp1252 codec
        with open(tpath, encoding="utf-8") as f:
            transcript = f.read().strip()

    video_tag = ""
    if video_path and os.path.exists(video_path):
        rel = os.path.relpath(video_path, out_dir)
        if not rel.startswith(".."):
            video_tag = '<video src="%s" controls playsinline></video>' % html.escape(rel)

    def _cell(f: str) -> str:
        name = os.path.basename(f)
        t = ts.get(name)
        tattr = ' data-t="%s"' % t if t is not None else ""
        # the filename is noise on the face of the thumbnail; the timestamp is
        # what you actually scan for, so that is what the chip shows
        stamp = ts_label.get(name, "")[:5]
        return ('<a href="frames/%s" target="_blank"%s title="%s">'
                '<img src="frames/%s" loading="lazy" alt="">'
                '<span>%s</span></a>'
                % (name, tattr, html.escape(name), name, html.escape(stamp)))

    cells = "".join(_cell(f) for f in frames)
    # "</" inside a <script> block would close it early, whatever the JSON says
    segs_json = json.dumps(segments, ensure_ascii=False).replace("</", "<\\/")

    # the folder is the only name this page has — "call-02-offers" beats a
    # generic "crv viewer" in a tab strip with three of these open
    title = os.path.basename(os.path.abspath(out_dir)).replace("_", " ")
    span = max((s["t"] for s in segments), default=0.0)
    meta = []
    if span:
        meta.append("%d min" % round(span / 60))
    if segments:
        meta.append("%d lines" % len(segments))
    meta.append("%d keyframes" % len(frames))

    page = _TEMPLATE
    for token, value in (
        ("__CELLS__", cells),
        ("__VIDEO__", video_tag),
        ("__NFRAMES__", str(len(frames))),
        ("__TITLE__", html.escape(title)),
        ("__META__", html.escape(" · ".join(meta))),
        ("__SEGS__", segs_json),
        ("__PLAIN__", json.dumps(transcript, ensure_ascii=False).replace("</", "<\\/")),
        ("__HASVID__", "true" if video_tag else "false"),
    ):
        page = page.replace(token, value)

    out = os.path.join(out_dir, "viewer.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    return out


_TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
  :root {
    --bg:#0b0a08; --surface:#141210; --surface-2:#1b1814; --line:#2a2521;
    --ink:#ece5d8; --ink-dim:#a2967f; --ink-faint:#6f6553;
    --accent:#f0b429; --accent-soft:rgba(240,180,41,.13);
    --radius:14px;
    --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    --sans:ui-sans-serif,-apple-system,"Segoe UI",Roboto,Inter,Helvetica,Arial,sans-serif;
    --serif:Charter,"Iowan Old Style",Georgia,"Times New Roman",serif;
  }
  * { margin:0; padding:0; box-sizing:border-box }
  html { -webkit-text-size-adjust:100% }
  body { background:var(--bg); color:var(--ink); font-family:var(--sans);
         font-size:14px; line-height:1.55; padding-bottom:48px;
         -webkit-font-smoothing:antialiased }
  a { color:inherit }
  ::selection { background:rgba(240,180,41,.28) }
  :focus-visible { outline:2px solid var(--accent); outline-offset:2px; border-radius:6px }
  ::-webkit-scrollbar { width:10px; height:10px }
  ::-webkit-scrollbar-track { background:transparent }
  ::-webkit-scrollbar-thumb { background:#2e2921; border-radius:8px; border:2px solid var(--bg) }
  ::-webkit-scrollbar-thumb:hover { background:#3d362b }

  header { position:sticky; top:0; z-index:30; display:flex; align-items:center;
           gap:16px; padding:13px 26px; background:rgba(11,10,8,.86);
           backdrop-filter:blur(12px); border-bottom:1px solid var(--line) }
  .brand { display:flex; align-items:baseline; gap:10px; min-width:0 }
  .brand b { color:var(--accent); font-size:13px; font-weight:650; letter-spacing:.02em;
             font-family:var(--mono) }
  .brand h1 { font-size:15px; font-weight:600; letter-spacing:-.01em; color:var(--ink);
              white-space:nowrap; overflow:hidden; text-overflow:ellipsis }
  .brand .meta { color:var(--ink-faint); font-size:12px; white-space:nowrap }
  header .sp { flex:1 }
  .lang { display:flex; gap:2px; background:var(--surface); border:1px solid var(--line);
          border-radius:999px; padding:2px }
  .lang a { cursor:pointer; color:var(--ink-faint); font-size:11px; padding:3px 9px;
            border-radius:999px; line-height:1.5 }
  .lang a:hover { color:var(--ink-dim) }
  .lang a.on { background:var(--accent-soft); color:var(--accent) }
  header .note { color:var(--ink-faint); font-size:11px; white-space:nowrap }

  main { max-width:1640px; margin:0 auto; padding:20px 26px;
         display:grid; grid-template-columns:minmax(0,1.05fr) minmax(0,1fr); gap:22px;
         align-items:start }
  .col { min-width:0 }
  .left { position:sticky; top:74px }

  video { width:100%; aspect-ratio:16/9; max-height:60vh; object-fit:contain;
          display:block; background:#000; border-radius:var(--radius);
          border:1px solid var(--line) }

  .panel { background:var(--surface); border:1px solid var(--line);
           border-radius:var(--radius); overflow:hidden }
  .phead { display:flex; align-items:center; gap:10px; flex-wrap:wrap;
           padding:11px 14px; border-bottom:1px solid var(--line); background:var(--surface-2) }
  .phead h2 { font-size:11px; font-weight:600; letter-spacing:.11em; text-transform:uppercase;
              color:var(--ink-dim); font-family:var(--mono) }
  .count { color:var(--ink-faint); font-size:11px; font-variant-numeric:tabular-nums;
           white-space:nowrap }

  .search { position:relative; flex:1 1 150px; min-width:130px; max-width:280px }
  .search svg { position:absolute; left:9px; top:50%; transform:translateY(-50%);
                width:13px; height:13px; stroke:var(--ink-faint); fill:none; stroke-width:2 }
  #q { width:100%; background:var(--bg); border:1px solid var(--line); border-radius:9px;
       color:var(--ink); font:inherit; font-size:12.5px; padding:6px 10px 6px 28px }
  #q::placeholder { color:var(--ink-faint) }
  #q:focus { outline:none; border-color:#4a4133; background:#100e0c }

  .seg { display:flex; gap:2px; background:var(--bg); border:1px solid var(--line);
         border-radius:999px; padding:2px }
  .seg label { position:relative; cursor:pointer; font-size:11.5px; color:var(--ink-faint);
               padding:4px 11px; border-radius:999px; user-select:none; line-height:1.4 }
  .seg label:hover { color:var(--ink-dim) }
  .seg input { position:absolute; opacity:0; pointer-events:none }
  .seg label.on { background:var(--accent-soft); color:var(--accent) }

  .tr { max-height:calc(100vh - 210px); overflow:auto; padding:6px }
  .tr.plain { white-space:pre-wrap; padding:20px; font-size:13.5px; line-height:1.8;
              color:var(--ink-dim) }

  .ln { display:grid; grid-template-columns:46px 1fr; gap:4px 12px; align-items:baseline;
        padding:7px 12px; border-radius:10px; cursor:pointer;
        border-left:2px solid transparent }
  .ln:hover { background:var(--surface-2) }
  .ln.on { background:var(--accent-soft); border-left-color:var(--accent) }
  .ln .t { font-family:var(--mono); font-size:10.5px; color:var(--ink-faint);
           font-variant-numeric:tabular-nums; padding-top:2px }
  .ln:hover .t, .ln.on .t { color:var(--accent) }
  .ln .sp { grid-column:2; justify-self:start; font-family:var(--mono); font-size:9.5px;
            letter-spacing:.09em; text-transform:uppercase; opacity:.9 }
  .ln .x { grid-column:2; color:#d5cbb8; font-size:14px; line-height:1.68 }
  .ln.on .x { color:var(--ink) }
  .ln.same .sp { display:none }
  .ln mark { background:rgba(240,180,41,.26); color:#ffe9b0; border-radius:3px; padding:0 1px }
  .s0 { color:var(--accent) } .s1 { color:#5fc8bd } .s2 { color:#b89ae8 }
  .s3 { color:#7fb3e8 } .s4 { color:#e89a9a } .s5 { color:#a8d68a }

  /* read mode: prose, not a log - timings stay in the DOM so clicking still seeks */
  .tr.read { padding:26px 34px; max-width:70ch; margin:0 auto }
  .tr.read .ln { display:block; padding:1px 0; border-left:0; border-radius:0 }
  .tr.read .ln:hover { background:transparent }
  .tr.read .ln.on { background:transparent }
  .tr.read .ln.on .x { box-shadow:inset 0 -1px 0 rgba(240,180,41,.55) }
  .tr.read .ln .t { display:none }
  .tr.read .ln .sp { display:block; margin:20px 0 3px; font-size:10px }
  .tr.read .ln.same .sp { display:none }
  .tr.read .ln .x { font-family:var(--serif); font-size:16.5px; line-height:1.9; color:#ded4c1 }

  details.kf { margin-top:18px }
  details.kf > summary { list-style:none; cursor:pointer; display:flex; align-items:center;
                         gap:9px; padding:9px 13px; background:var(--surface);
                         border:1px solid var(--line); border-radius:11px;
                         font-size:11px; letter-spacing:.11em; text-transform:uppercase;
                         color:var(--ink-dim); font-family:var(--mono) }
  details.kf > summary::-webkit-details-marker { display:none }
  details.kf > summary:hover { color:var(--ink) }
  details.kf > summary .chev { transition:transform .18s ease; color:var(--ink-faint) }
  details.kf[open] > summary .chev { transform:rotate(90deg) }
  details.kf > summary .hint { margin-left:auto; text-transform:none; letter-spacing:0;
                                color:var(--ink-faint); font-size:11px }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(124px,1fr)); gap:7px;
          margin-top:11px; max-height:46vh; overflow:auto; padding:1px }
  .grid a { position:relative; display:block; border:1px solid var(--line);
            border-radius:9px; overflow:hidden; background:#000; line-height:0 }
  .grid a:hover { border-color:#4e4434 }
  .grid img { width:100%; display:block; transition:opacity .15s ease }
  .grid a:hover img { opacity:.82 }
  .grid span { position:absolute; right:5px; bottom:5px; font-family:var(--mono);
               font-size:9.5px; line-height:1.6; color:#e4dac6; background:rgba(8,7,5,.76);
               padding:1px 5px; border-radius:5px; letter-spacing:.02em }

  #lb { position:fixed; inset:0; display:none; background:rgba(8,7,5,.95); z-index:60;
        align-items:center; justify-content:center; flex-direction:column; gap:14px;
        padding:28px }
  #lb.open { display:flex }
  #lb img { max-width:92vw; max-height:80vh; border-radius:11px; border:1px solid var(--line) }
  #lb .cap { color:var(--ink-dim); font-size:12px; font-family:var(--mono) }
  #lb .hint { color:var(--ink-faint); font-size:11px }
  #lb .x { position:absolute; top:16px; right:22px; color:var(--ink-dim); font-size:26px;
           cursor:pointer; line-height:1; padding:6px }
  #lb .x:hover { color:var(--ink) }
  #lb .nav { position:absolute; top:50%; transform:translateY(-50%); font-size:30px;
             color:var(--ink-faint); cursor:pointer; padding:22px; user-select:none }
  #lb .nav:hover { color:var(--ink) }
  #lb .prev { left:8px } #lb .next { right:8px }
  #lb-jump { color:var(--accent); cursor:pointer; font-size:12.5px; display:none }

  @media (max-width:1000px) {
    main { grid-template-columns:1fr; padding:16px }
    .left { position:static }
    .tr { max-height:none }
    header { padding:12px 16px }
    .brand .meta, header .note { display:none }
  }
  @media (prefers-reduced-motion:reduce) { * { transition:none !important } }
</style></head><body>
<header>
  <div class="brand">
    <b>crv</b>
    <h1>__TITLE__</h1>
    <span class="meta">__META__</span>
  </div>
  <div class="sp"></div>
  <span class="note" data-i="local">runs 100% locally</span>
  <nav class="lang">
    <a data-lang="en">EN</a><a data-lang="zh_tw">繁中</a><a data-lang="zh_cn">简中</a>
  </nav>
</header>
<main>
  <div class="col left">
    __VIDEO__
    <details class="kf" open>
      <summary>
        <span class="chev">&#9656;</span>
        <span data-i="kf">Keyframes</span>
        <span class="hint">__NFRAMES__ &middot; <span data-i="kfhint">what the model sees</span></span>
      </summary>
      <div class="grid">__CELLS__</div>
    </details>
  </div>
  <div class="col">
    <div class="panel">
      <div class="phead">
        <h2 data-i="tr">Transcript</h2>
        <label class="search">
          <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"></circle><path d="M20 20l-3.5-3.5"></path></svg>
          <input id="q" placeholder="search" data-i2="ph">
        </label>
        <span class="count" id="cnt"></span>
        <div class="seg">
          <label id="read-l"><input type="checkbox" id="read"><span data-i="read">read</span></label>
          <label id="foll-l" class="on"><input type="checkbox" id="foll" checked><span data-i="follow">follow</span></label>
        </div>
      </div>
      <div class="tr" id="tr"></div>
    </div>
  </div>
</main>
<div id="lb">
  <div class="x" onclick="lbClose()">&times;</div>
  <div class="nav prev" onclick="lbStep(-1)">&#8249;</div>
  <img id="lb-img" alt="">
  <div class="cap" id="lb-cap"></div>
  <a id="lb-jump"></a>
  <div class="hint">&larr; &rarr; browse &middot; ESC close</div>
  <div class="nav next" onclick="lbStep(1)">&#8250;</div>
</div>
<script>
var SEGS = __SEGS__;
var PLAIN = __PLAIN__;
var HASVID = __HASVID__;

/* ---- clickable transcript: click a line, the video seeks there ---- */
(function () {
  var vid = document.querySelector("video"), box = document.getElementById("tr");
  var cnt = document.getElementById("cnt"), q = document.getElementById("q");
  var foll = document.getElementById("foll"), read = document.getElementById("read");

  if (!SEGS.length) {
    box.className = PLAIN ? "tr plain" : "tr plain none";
    box.textContent = PLAIN || "(no transcript)";
    q.style.display = "none";
    foll.parentNode.style.display = "none";
    read.parentNode.style.display = "none";
    return;
  }

  function fmt(s) {
    var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = Math.floor(s % 60);
    var mm = (m < 10 ? "0" : "") + m, ss = (x < 10 ? "0" : "") + x;
    return h ? h + ":" + mm + ":" + ss : mm + ":" + ss;
  }
  // stable colour per speaker, in order of first appearance
  var spk = {}, nspk = 0;
  SEGS.forEach(function (s) { if (s.s && !(s.s in spk)) spk[s.s] = nspk++; });
  function shortName(n) { var m = /(\d+)\s*$/.exec(n); return m ? "S" + m[1] : n; }

  var rows = SEGS.map(function (s, i) {
    var r = document.createElement("div");
    r.className = "ln" + (i && SEGS[i - 1].s === s.s ? " same" : "");
    var t = document.createElement("span");
    t.className = "t"; t.textContent = fmt(s.t);
    r.appendChild(t);
    if (s.s) {
      var sp = document.createElement("span");
      sp.className = "sp s" + (spk[s.s] % 6);
      sp.textContent = shortName(s.s);
      sp.title = s.s;
      r.appendChild(sp);
    }
    var x = document.createElement("span");
    x.className = "x"; x.textContent = s.x;
    r.appendChild(x);
    r.addEventListener("click", function () {
      if (!HASVID || !vid) return;
      vid.currentTime = s.t;
      vid.play();
    });
    box.appendChild(r);
    return r;
  });
  cnt.textContent = SEGS.length + " lines";
  if (!HASVID) box.title = "no video in this folder — timestamps shown, seeking disabled";

  /* ---- pill toggles: the label carries the lit state ---- */
  function paint(cb) { cb.parentNode.classList.toggle("on", cb.checked); }
  foll.addEventListener("change", function () { paint(foll); });

  /* ---- read mode: same lines, reflowed as prose ---- */
  read.addEventListener("change", function () {
    box.classList.toggle("read", read.checked);
    paint(read);
    localStorage.setItem("crv_read", read.checked ? "1" : "");
  });
  if (localStorage.getItem("crv_read")) { read.checked = true; box.classList.add("read"); }
  paint(read);
  paint(foll);

  /* ---- highlight the line under the playhead ---- */
  var cur = -1;
  function locate(time) {            // last segment whose start <= time
    var lo = 0, hi = SEGS.length - 1, best = -1;
    while (lo <= hi) {
      var mid = (lo + hi) >> 1;
      if (SEGS[mid].t <= time) { best = mid; lo = mid + 1; } else { hi = mid - 1; }
    }
    return best;
  }
  if (vid) {
    vid.addEventListener("timeupdate", function () {
      var i = locate(vid.currentTime);
      if (i === cur) return;
      if (cur >= 0 && rows[cur]) rows[cur].classList.remove("on");
      cur = i;
      if (cur < 0 || !rows[cur]) return;
      rows[cur].classList.add("on");
      if (!foll.checked || rows[cur].style.display === "none") return;
      var rb = rows[cur].getBoundingClientRect(), bb = box.getBoundingClientRect();
      if (rb.top < bb.top + 8 || rb.bottom > bb.bottom - 8) {
        box.scrollTop += rb.top - bb.top - box.clientHeight / 3;
      }
    });
  }

  /* ---- search: filter to matching lines, highlight the hit ---- */
  var timer = null;
  q.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(function () {
      var term = q.value.trim().toLowerCase(), hits = 0;
      rows.forEach(function (r, i) {
        var txt = SEGS[i].x, hit = !term || txt.toLowerCase().indexOf(term) >= 0;
        r.style.display = hit ? "" : "none";
        if (hit) hits++;
        var cell = r.querySelector(".x");
        if (!term) { cell.textContent = txt; return; }
        cell.textContent = "";
        var low = txt.toLowerCase(), from = 0, at;
        while ((at = low.indexOf(term, from)) >= 0) {
          cell.appendChild(document.createTextNode(txt.slice(from, at)));
          var mk = document.createElement("mark");
          mk.textContent = txt.slice(at, at + term.length);
          cell.appendChild(mk);
          from = at + term.length;
        }
        cell.appendChild(document.createTextNode(txt.slice(from)));
      });
      cnt.textContent = term ? hits + " / " + SEGS.length : SEGS.length + " lines";
    }, 120);
  });
})();

/* ---- keyframe lightbox ---- */
(function () {
  var links = Array.prototype.slice.call(document.querySelectorAll(".grid a"));
  var idx = -1, lb = document.getElementById("lb"),
      im = document.getElementById("lb-img"), cap = document.getElementById("lb-cap");
  var jump = document.getElementById("lb-jump"), vid = document.querySelector("video");
  function show(i) {
    idx = (i + links.length) % links.length;
    im.src = links[idx].getAttribute("href");
    cap.textContent = links[idx].querySelector("span").textContent + "  (" + (idx + 1) + "/" + links.length + ")";
    var t = links[idx].getAttribute("data-t");
    if (vid && t !== null) {
      jump.style.display = "inline";
      jump.textContent = "▶ play video from here";
      jump.onclick = function () { vid.currentTime = parseFloat(t); lbClose(); vid.play(); vid.scrollIntoView({behavior:"smooth"}); };
    } else { jump.style.display = "none"; }
    lb.classList.add("open");
  }
  window.lbClose = function () { lb.classList.remove("open"); };
  window.lbStep = function (d) { show(idx + d); };
  links.forEach(function (a, i) {
    a.addEventListener("click", function (e) { e.preventDefault(); show(i); });
  });
  lb.addEventListener("click", function (e) { if (e.target === lb) lbClose(); });
  document.addEventListener("keydown", function (e) {
    if (!lb.classList.contains("open")) return;
    if (e.key === "Escape") lbClose();
    else if (e.key === "ArrowLeft") lbStep(-1);
    else if (e.key === "ArrowRight") lbStep(1);
  });
})();

/* ---- language ---- */
(function () {
  var D = {
    zh_tw: { local:"全程本機執行", kf:"關鍵幀", kfhint:"模型看到的畫面", tr:"逐字稿", follow:"跟隨播放", read:"閱讀", ph:"搜尋" },
    zh_cn: { local:"全程本机运行", kf:"关键帧", kfhint:"模型看到的画面", tr:"逐字稿", follow:"跟随播放", read:"阅读", ph:"搜索" },
    en:    { local:"runs 100% locally", kf:"Keyframes", kfhint:"what the model sees", tr:"Transcript", follow:"follow", read:"read", ph:"search" }
  };
  // v2 key: the old one was written on every load, so a first visit persisted
  // the default language and the page could never pick a different one again
  var KEY = "crv_lang2";
  function set(l, remember) {
    if (remember) localStorage.setItem(KEY, l);
    document.querySelectorAll("[data-i]").forEach(function (el) { el.textContent = D[l][el.dataset.i]; });
    document.querySelectorAll("[data-i2]").forEach(function (el) { el.placeholder = D[l][el.dataset.i2]; });
    document.querySelectorAll(".lang a").forEach(function (a) { a.classList.toggle("on", a.dataset.lang === l); });
  }
  document.querySelectorAll(".lang a").forEach(function (a) {
    a.addEventListener("click", function () { set(a.dataset.lang, true); });
  });
  set(localStorage.getItem(KEY) || "en", false);
})();
</script>
</body></html>
"""
