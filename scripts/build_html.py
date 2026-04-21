"""
build_html.py v3.1
從 scraper/output/index.json 產生 docs/index.html
文章內容嵌在 JSON 內，點擊用 modal 展開，不依賴任何 .txt 連結
"""

import json, re
from pathlib import Path

INDEX_JSON = Path("scraper/output/index.json")
DOCS_DIR   = Path("docs")
DOCS_DIR.mkdir(exist_ok=True)

TAG_META = {
    "announcement":     ("&#128226;", "教務處公告",     "教務處最新官方公告",       "#2471a3"),
    "add_drop":         ("&#128260;", "加退選公告",     "加選、退選、停修說明",     "#c0392b"),
    "cross_school":     ("&#127981;", "校際選課",       "優久聯盟、跨校選課",       "#27ae60"),
    "ai_alliance":      ("&#129302;", "AI 聯盟課程",    "TAICA 人工智慧聯盟課程",   "#2980b9"),
    "double_major":     ("&#127891;", "輔系雙主修",     "輔系、雙主修、學分學程",   "#8e44ad"),
    "remedial":         ("&#128221;", "暑修補修重修",   "暑修、補修、重修課程",     "#e67e22"),
    "class_change":     ("&#9888;",   "停課調課補課",   "停課、補課、調課通知",     "#e74c3c"),
    "freshman":         ("&#127807;", "新生選課說明",   "大一新生選課注意事項",     "#16a085"),
    "english":          ("&#127760;", "英語教學中心",   "英語課程 ELC 選課資訊",    "#1abc9c"),
    "course_structure": ("&#128218;", "開課與課程架構", "各系所課程結構",           "#d35400"),
    "other":            ("&#128196;", "其他",           "其餘相關資訊",             "#7f8c8d"),
}
TAG_ORDER = [
    "announcement","add_drop","cross_school","ai_alliance",
    "double_major","remedial","class_change",
    "freshman","english","course_structure","other",
]
RECLASSIFY_RULES = [
    (r"加退選|加選|退選|停修|Withdraw",  "add_drop"),
    (r"跨校|校際|優久|聯盟跨",          "cross_school"),
    (r"AI|人工智慧|TAICA|ai_alliance",   "ai_alliance"),
    (r"輔系|雙主修|學分學程|eForm",      "double_major"),
    (r"暑修|補修|重修|make.?up|summer",  "remedial"),
    (r"停課|停班|補課|調課|cancel",      "class_change"),
    (r"新生|freshman|a01-04",           "freshman"),
    (r"elc\.mcu|英語教學|ELC|english",  "english"),
]

def reclassify(doc):
    base = doc.get("tag","other")
    if base != "announcement":
        return base
    text = (doc.get("title","") + " " + doc.get("url","")).lower()
    for p, t in RECLASSIFY_RULES:
        if re.search(p, text, re.IGNORECASE):
            return t
    return base

def clean_title(doc):
    t = doc.get("title","").strip()
    if t.startswith("https://") or not t:
        url = doc.get("url","")
        f = url.rstrip("/").split("/")[-1]
        f = re.sub(r"CourseStructure-?(\d+)(-\d+)?", r"課程架構-\1", f)
        return f.replace(".pdf","").replace("-"," ").replace("_"," ") or url
    return t

def build():
    if not INDEX_JSON.exists():
        print("❌ index.json 不存在"); return

    data      = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    docs      = data.get("documents", [])
    generated = data.get("generated_at", "")
    total     = len(docs)

    for d in docs:
        d["_title"] = clean_title(d)
        d["_tag"]   = reclassify(d)

    slim = [{
        "id":        d.get("id",""),
        "url":       d["url"],
        "title":     d["_title"],
        "scraped_at":d.get("scraped_at","")[:10],
        "tag":       d["_tag"],
        "type":      d.get("type",""),
        "semester":  d.get("semester",""),
        "content":   d.get("content",""),
    } for d in docs]

    docs_js = json.dumps(slim, ensure_ascii=False)

    tag_counts = {}
    for d in slim:
        tag_counts[d["tag"]] = tag_counts.get(d["tag"], 0) + 1

    filter_btns = f'<button class="filter-btn active" data-cat="all">全部 <span class="btn-count">{total}</span></button>\n'
    for tag in TAG_ORDER:
        if tag not in tag_counts: continue
        icon, label, _, _ = TAG_META.get(tag, ("📄", tag, "", ""))
        filter_btns += f'    <button class="filter-btn" data-cat="{tag}">{icon} {label} <span class="btn-count">{tag_counts[tag]}</span></button>\n'

    sections_html = ""
    for tag in TAG_ORDER:
        if tag not in tag_counts: continue
        icon, label, desc, color = TAG_META.get(tag, ("📄", tag, "", "#555"))
        sections_html += f"""
  <div class="cat-section" data-cat="{tag}">
    <div class="cat-header" style="--accent:{color}">
      <h2 class="cat-title">{icon} {label}</h2>
      <span class="cat-count" id="count-{tag}">{tag_counts[tag]}</span>
      <span class="cat-desc">{desc}</span>
    </div>
    <div class="card-grid" id="grid-{tag}"></div>
  </div>"""

    tags_js = json.dumps(TAG_ORDER)

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>銘傳大學選課資訊 | 自動爬蟲</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;600;700&display=swap" rel="stylesheet"/>
  <style>
    *,*::before,*::after{{box-sizing:border-box}}
    :root{{
      --blue:#1d5fa8;--blue-lt:#e8f0fb;--blue-dk:#153f72;
      --teal:#0d8c6d;--red:#c0392b;--bg:#f0f4f8;
      --surface:#fff;--border:#d0dbe8;--text:#1e2d40;--muted:#7a94aa;
    }}
    body{{font-family:"Noto Sans TC","PingFang TC","Microsoft JhengHei",sans-serif;
          margin:0;padding:0;background:var(--bg);color:var(--text);min-height:100vh}}
    /* Header */
    header{{background:linear-gradient(135deg,#0f2d57 0%,#1d5fa8 55%,#0d8c6d 100%);
            color:#fff;padding:2.2rem 1.5rem 1.6rem;text-align:center;position:relative;overflow:hidden}}
    header::before{{content:'';position:absolute;inset:0;opacity:.05;
      background-image:radial-gradient(circle,#fff 1px,transparent 1px);background-size:28px 28px}}
    header h1{{margin:0 0 .4rem;font-size:1.85rem;font-weight:700;position:relative}}
    header p{{margin:0;opacity:.8;font-size:.92rem;position:relative}}
    .meta-chips{{margin-top:1rem;display:flex;gap:.5rem;flex-wrap:wrap;justify-content:center;position:relative}}
    .chip{{display:inline-flex;align-items:center;gap:.4rem;
           background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.22);
           border-radius:999px;padding:.28rem .95rem;font-size:.78rem}}
    .pulse{{width:8px;height:8px;background:#2ecc71;border-radius:50%;
            animation:pulse 1.8s ease-in-out infinite;flex-shrink:0}}
    @keyframes pulse{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.5;transform:scale(.75)}}}}
    /* Controls */
    .controls-wrap{{position:sticky;top:0;z-index:100;background:var(--surface);
                    box-shadow:0 2px 10px rgba(0,0,0,.08)}}
    .controls{{max-width:1120px;margin:0 auto;padding:.85rem 1.2rem;display:flex;gap:.7rem;flex-wrap:wrap;align-items:center}}
    .search-wrap{{flex:1 1 220px;position:relative}}
    .search-wrap input{{width:100%;padding:.55rem .9rem .55rem 2.5rem;border:1.5px solid var(--border);
                        border-radius:9px;font-size:.9rem;outline:none;color:var(--text);
                        font-family:inherit;transition:border-color .15s,box-shadow .15s}}
    .search-wrap input:focus{{border-color:var(--blue);box-shadow:0 0 0 3px rgba(29,95,168,.12)}}
    .search-icon{{position:absolute;left:.8rem;top:50%;transform:translateY(-50%);color:var(--muted);pointer-events:none;font-size:1rem}}
    .filter-row{{display:flex;gap:.4rem;flex-wrap:wrap}}
    .filter-btn,.type-btn{{padding:.38rem .9rem;border-radius:20px;border:1.5px solid var(--border);
                 background:var(--surface);font-size:.78rem;cursor:pointer;color:#555;
                 transition:all .15s;user-select:none;font-family:inherit}}
    .filter-btn:hover,.type-btn:hover{{border-color:var(--blue);color:var(--blue)}}
    .filter-btn.active{{background:var(--blue);border-color:var(--blue);color:#fff;font-weight:700}}
    .btn-count{{background:rgba(255,255,255,.25);border-radius:99px;padding:.03rem .42rem;font-size:.7rem;margin-left:.18rem}}
    .filter-btn:not(.active) .btn-count{{background:var(--blue-lt);color:var(--blue)}}
    .type-btn.pdf.active{{background:#fde8e8;border-color:var(--red);color:var(--red);font-weight:700}}
    .type-btn.web.active{{background:#e8f5e9;border-color:#2e7d32;color:#2e7d32;font-weight:700}}
    .results-bar{{max-width:1120px;margin:.5rem auto 0;padding:0 1.2rem;font-size:.8rem;color:var(--muted)}}
    /* Main */
    main{{max-width:1120px;margin:.9rem auto 4rem;padding:0 1.2rem}}
    .cat-section{{margin-bottom:1.8rem}}
    .cat-header{{display:flex;align-items:center;gap:.55rem;margin-bottom:.7rem;
                 border-left:4px solid var(--accent,var(--blue));padding-left:.7rem}}
    .cat-title{{font-size:1rem;font-weight:700;color:var(--blue-dk);margin:0}}
    .cat-count{{background:var(--blue-lt);color:var(--blue);border-radius:999px;
                padding:.1rem .55rem;font-size:.72rem;font-weight:700}}
    .cat-desc{{font-size:.76rem;color:var(--muted);margin-left:.15rem}}
    /* Cards */
    .card-grid{{display:grid;gap:.5rem}}
    .card{{background:var(--surface);border-radius:11px;box-shadow:0 1px 4px rgba(0,0,0,.06);
           padding:.8rem 1.05rem;display:grid;
           grid-template-columns:auto 1fr auto;gap:.4rem .9rem;align-items:start;
           transition:box-shadow .15s,transform .15s;border:1px solid transparent}}
    .card:hover{{box-shadow:0 5px 18px rgba(0,0,0,.1);transform:translateY(-1px);border-color:var(--border)}}
    .card.hidden{{display:none}}
    .badge{{display:inline-block;padding:.13rem .48rem;border-radius:4px;
            font-size:.68rem;font-weight:700;white-space:nowrap;margin-top:.18rem}}
    .badge.pdf{{background:#fde8e8;color:var(--red)}}
    .badge.webpage{{background:#e8f5e9;color:#2e7d32}}
    .badge.doc{{background:var(--blue-lt);color:var(--blue)}}
    .semester-tag{{display:inline-block;margin-left:.4rem;padding:.1rem .4rem;
                   border-radius:4px;font-size:.65rem;background:#fff8e1;color:#b7691a;font-weight:600}}
    .new-dot{{display:inline-block;width:7px;height:7px;background:#e74c3c;
              border-radius:50%;margin-left:.5rem;vertical-align:middle}}
    .card-body{{min-width:0}}
    .card-title{{font-size:.87rem;font-weight:600;color:var(--blue-dk);margin:0 0 .25rem;line-height:1.45}}
    .card-meta{{font-size:.72rem;color:var(--muted)}}
    .card-meta a{{color:var(--blue);text-decoration:none}}
    .card-meta a:hover{{text-decoration:underline}}
    .card-actions{{display:flex;flex-direction:column;align-items:flex-end;gap:.3rem}}
    .btn-link{{display:inline-block;padding:.25rem .68rem;border-radius:6px;
               font-size:.72rem;text-decoration:none;white-space:nowrap;font-family:inherit;cursor:pointer;
               transition:background .12s;border:none}}
    .btn-view{{background:var(--blue-lt);color:var(--blue)}}
    .btn-view:hover{{background:#c8daef}}
    .btn-src{{background:var(--bg);color:#555}}
    .btn-src:hover{{background:#dde5ee}}
    .empty{{text-align:center;padding:3.5rem 1rem;color:var(--muted);font-size:.9rem;display:none}}
    .empty.show{{display:block}}
    footer{{text-align:center;color:var(--muted);font-size:.75rem;margin:0 0 2.5rem;padding:0 1rem;line-height:1.9}}
    /* Modal */
    .modal-overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);
                    z-index:1000;align-items:center;justify-content:center;padding:1rem}}
    .modal-overlay.open{{display:flex}}
    .modal{{background:var(--surface);border-radius:14px;width:100%;max-width:760px;
            max-height:88vh;display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,.25)}}
    .modal-head{{padding:1.1rem 1.4rem .9rem;border-bottom:1px solid var(--border);display:flex;align-items:flex-start;gap:.8rem}}
    .modal-head h3{{margin:0;font-size:1rem;font-weight:700;color:var(--blue-dk);flex:1;line-height:1.4}}
    .modal-close{{background:none;border:none;font-size:1.4rem;cursor:pointer;color:var(--muted);
                  padding:.1rem .3rem;border-radius:5px;line-height:1;flex-shrink:0}}
    .modal-close:hover{{background:var(--bg);color:var(--text)}}
    .modal-meta{{padding:.6rem 1.4rem;font-size:.76rem;color:var(--muted);border-bottom:1px solid var(--border);
                 display:flex;gap:1rem;flex-wrap:wrap;align-items:center}}
    .modal-meta a{{color:var(--blue);text-decoration:none}}
    .modal-meta a:hover{{text-decoration:underline}}
    .modal-body{{padding:1.1rem 1.4rem;overflow-y:auto;flex:1}}
    .modal-body pre{{white-space:pre-wrap;word-break:break-word;font-family:inherit;
                     font-size:.85rem;line-height:1.75;color:var(--text);margin:0}}
    .modal-empty{{color:var(--muted);font-size:.9rem;text-align:center;padding:2rem 0}}
    @media(max-width:600px){{
      header h1{{font-size:1.35rem}}
      .card{{grid-template-columns:auto 1fr}}
      .card-actions{{flex-direction:row;flex-wrap:wrap;grid-column:1/-1}}
      .modal{{max-height:95vh;border-radius:10px 10px 0 0;position:fixed;bottom:0;top:auto;width:100%;max-width:100%}}
      .modal-overlay{{align-items:flex-end;padding:0}}
    }}
  </style>
</head>
<body>

<header>
  <h1>&#127979; 銘傳大學選課資訊自動爬蟲</h1>
  <p>自動爬取教務處、英語教學中心等官方頁面的最新選課公告</p>
  <div class="meta-chips">
    <span class="chip">&#128197; 最後更新：{generated[:19]}</span>
    <span class="chip">&#128194; 共 {total} 份文件</span>
    <span class="chip"><span class="pulse"></span> 每日自動更新 via GitHub Actions</span>
  </div>
</header>

<div class="controls-wrap">
  <div class="controls">
    <div class="search-wrap">
      <span class="search-icon">&#128269;</span>
      <input type="text" id="searchInput" placeholder="搜尋標題、學年期、來源…" autocomplete="off"/>
    </div>
    <div class="filter-row">
      {filter_btns}
    </div>
    <div class="filter-row">
      <button class="type-btn pdf" data-type="pdf">&#128196; PDF</button>
      <button class="type-btn web" data-type="webpage">&#127760; 網頁</button>
    </div>
  </div>
</div>

<div class="results-bar" id="resultsBar">顯示 {total} / {total} 筆</div>

<main id="mainContent">
  {sections_html}
  <div class="empty" id="emptyState">&#128533; 找不到符合條件的文件</div>
</main>

<footer>
  資料來源：銘傳大學各官方網站 ・ 每日自動更新（GitHub Actions 08:00 / 20:00 台灣時間）<br/>
  本頁僅供資訊彙整，請以各官方網站公告為準。
</footer>

<!-- Modal -->
<div class="modal-overlay" id="modalOverlay">
  <div class="modal" role="dialog" aria-modal="true">
    <div class="modal-head">
      <h3 id="modalTitle"></h3>
      <button class="modal-close" id="modalClose" aria-label="關閉">&#10005;</button>
    </div>
    <div class="modal-meta" id="modalMeta"></div>
    <div class="modal-body">
      <pre id="modalContent"></pre>
    </div>
  </div>
</div>

<script>
const DOCS = {docs_js};
const TAGS = {tags_js};
const NOW  = Date.now();

function isNew(d) {{ return d && (NOW - new Date(d).getTime()) < 7*86400000; }}
function badgeClass(t) {{ return t==='pdf'?'pdf':t==='webpage'?'webpage':'doc'; }}
function badgeLabel(t) {{ return t==='pdf'?'PDF':t==='webpage'?'網頁':t.toUpperCase(); }}

/* ── 渲染卡片 ── */
function renderCards() {{
  TAGS.forEach(tag => {{
    const grid = document.getElementById('grid-'+tag);
    if (!grid) return;
    grid.innerHTML = DOCS.filter(d => d.tag===tag).map(item => {{
      const bc  = badgeClass(item.type);
      const bl  = badgeLabel(item.type);
      const nd  = isNew(item.scraped_at) ? '<span class="new-dot" title="7天內新增"></span>' : '';
      const sem = item.semester ? `<span class="semester-tag">${{item.semester}}</span>` : '';
      return `<div class="card" data-tag="${{item.tag}}" data-type="${{item.type}}"
                   data-search="${{(item.title+' '+item.url+' '+item.semester).toLowerCase()}}"
                   data-id="${{item.id}}">
        <div><span class="badge ${{bc}}">${{bl}}</span></div>
        <div class="card-body">
          <p class="card-title">${{item.title}}${{nd}}${{sem}}</p>
          <span class="card-meta">爬取：${{item.scraped_at}} &nbsp;·&nbsp;
            <a href="${{item.url}}" target="_blank" rel="noopener">原始頁面 ↗</a>
          </span>
        </div>
        <div class="card-actions">
          <button class="btn-link btn-view" onclick="openModal('${{item.id}}')">&#128196; 查看內文</button>
          <a class="btn-link btn-src" href="${{item.url}}" target="_blank" rel="noopener">&#128279; 原始連結</a>
        </div>
      </div>`;
    }}).join('');
  }});
}}

/* ── Modal ── */
const overlay = document.getElementById('modalOverlay');
const docMap  = Object.fromEntries(DOCS.map(d => [d.id, d]));

function openModal(id) {{
  const d = docMap[id];
  if (!d) return;
  document.getElementById('modalTitle').textContent = d.title;
  document.getElementById('modalMeta').innerHTML =
    `<span>&#128197; ${{d.scraped_at}}</span>` +
    (d.semester ? `<span>&#127979; ${{d.semester}}</span>` : '') +
    `<span><a href="${{d.url}}" target="_blank" rel="noopener">&#128279; 原始頁面 ↗</a></span>`;
  const pre = document.getElementById('modalContent');
  if (d.content && d.content.trim()) {{
    pre.textContent = d.content;
  }} else {{
    pre.innerHTML = '<span class="modal-empty">（此頁面無擷取到文字內容）</span>';
  }}
  overlay.classList.add('open');
  document.body.style.overflow = 'hidden';
}}

function closeModal() {{
  overlay.classList.remove('open');
  document.body.style.overflow = '';
}}

document.getElementById('modalClose').addEventListener('click', closeModal);
overlay.addEventListener('click', e => {{ if (e.target === overlay) closeModal(); }});
document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeModal(); }});

/* ── 篩選 ── */
let activeCat='all', activeType=null, searchQ='';

function applyFilters() {{
  const cards = document.querySelectorAll('.card');
  let visible = 0;
  TAGS.forEach(tag => {{
    const sec = document.querySelector('.cat-section[data-cat="'+tag+'"]');
    if (sec) sec.style.display = (activeCat==='all'||activeCat===tag) ? '' : 'none';
  }});
  cards.forEach(card => {{
    const ok = (activeCat==='all'||activeCat===card.dataset.tag)
            && (!activeType||card.dataset.type===activeType)
            && (!searchQ||card.dataset.search.includes(searchQ));
    card.classList.toggle('hidden', !ok);
    if (ok) visible++;
  }});
  TAGS.forEach(tag => {{
    const el = document.getElementById('count-'+tag);
    if (el) el.textContent = document.querySelectorAll(`.cat-section[data-cat="${{tag}}"] .card:not(.hidden)`).length;
  }});
  document.getElementById('resultsBar').textContent = `顯示 ${{visible}} / ${{DOCS.length}} 筆`;
  document.getElementById('emptyState').classList.toggle('show', visible===0);
}}

document.querySelectorAll('.filter-btn').forEach(btn => btn.addEventListener('click', () => {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active'); activeCat = btn.dataset.cat; applyFilters();
}}));
document.querySelectorAll('.type-btn').forEach(btn => btn.addEventListener('click', () => {{
  if (btn.classList.contains('active')) {{ btn.classList.remove('active'); activeType=null; }}
  else {{ document.querySelectorAll('.type-btn').forEach(b=>b.classList.remove('active'));
          btn.classList.add('active'); activeType=btn.dataset.type; }}
  applyFilters();
}}));
let st;
document.getElementById('searchInput').addEventListener('input', e => {{
  clearTimeout(st); st = setTimeout(() => {{ searchQ=e.target.value.trim().toLowerCase(); applyFilters(); }}, 150);
}});

renderCards();
applyFilters();
</script>
</body>
</html>"""

    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"✅ docs/index.html 已產生（{total} 份文件，Modal 內文展開版）")

if __name__ == "__main__":
    build()
