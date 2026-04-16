"""
根據 output/index.json 產生 docs/index.html（GitHub Pages 入口）
v2.1：支援細化分類、分類篩選、類型篩選、關鍵字搜尋、即時 Banner
"""

import json
import re
from pathlib import Path

INDEX_JSON = Path("scraper/output/index.json")
DOCS_DIR   = Path("docs")
DOCS_DIR.mkdir(exist_ok=True)

# ── 細化標籤定義 ───────────────────────────────────────────────────────────────
# tag → (emoji_entity, 中文標籤, 說明文字, 顏色-accent)
TAG_META = {
    # 原有四大類
    "announcement":          ("&#128226;", "教務處公告",      "教務處最新官方公告與通知",          "#2471a3"),
    "freshman":              ("&#127891;", "新生選課說明",    "大一新生選課相關注意事項",          "#8e44ad"),
    "english":               ("&#127760;", "英語教學中心",    "英語課程、ELC 選課資訊",            "#16a085"),
    "course_structure":      ("&#128218;", "開課與課程架構",  "各系所課程結構與學分規劃",          "#d35400"),
    # 細化子類（由爬蟲升級後產生，build_html 也需支援）
    "cross_school":          ("&#127981;", "校際選課",        "優久聯盟、跨校選課相關公告",        "#27ae60"),
    "add_drop":              ("&#128260;", "加退選公告",      "加選、退選、停修等操作說明",        "#c0392b"),
    "ai_alliance":           ("&#129302;", "AI 聯盟課程",     "台灣大專院校 AI 聯盟主導課程",      "#2980b9"),
    "double_major":          ("&#127891;", "輔系雙主修",      "輔系、雙主修、學分學程申請",        "#8e44ad"),
    "other":                 ("&#128196;", "其他",            "其餘相關資訊",                      "#7f8c8d"),
}

# 顯示順序
TAG_ORDER = [
    "announcement", "add_drop", "cross_school", "ai_alliance",
    "double_major", "freshman", "english", "course_structure", "other",
]


# ── 自動細化分類 ──────────────────────────────────────────────────────────────
RECLASSIFY_RULES = [
    # (pattern_in_title_or_url, new_tag)
    (r"跨校|校際|優久|聯盟跨",                 "cross_school"),
    (r"加退選|加選|退選|停修|Withdraw",         "add_drop"),
    (r"AI|人工智慧|TAICA|ai_alliance",          "ai_alliance"),
    (r"輔系|雙主修|學分學程|eForm",             "double_major"),
    (r"新生|freshman|a01-04",                   "freshman"),
    (r"elc\.mcu|英語教學|ELC|english",          "english"),
]

def reclassify(doc: dict) -> str:
    """根據標題 + URL 細化 tag，原 tag 保底。"""
    base = doc.get("tag", "other")
    text = (doc.get("title", "") + " " + doc.get("url", "")).lower()
    # 只細化 announcement 層
    if base == "announcement":
        for pattern, new_tag in RECLASSIFY_RULES:
            if re.search(pattern, text, re.IGNORECASE):
                return new_tag
    return base


def clean_title(doc: dict) -> str:
    title = doc.get("title", "").strip()
    if title.startswith("https://") or not title:
        url = doc.get("url", "")
        fname = url.rstrip("/").split("/")[-1]
        fname = re.sub(r"CourseStructure-?(\d+)(-\d+)?", r"課程架構-\1", fname)
        fname = fname.replace(".pdf", "").replace("-", " ").replace("_", " ")
        return fname or url
    return title


# ── HTML 建置 ─────────────────────────────────────────────────────────────────

def build() -> None:
    if not INDEX_JSON.exists():
        print("❌ index.json 不存在，略過 HTML 建置")
        return

    data    = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    docs    = data.get("documents", [])
    generated = data.get("generated_at", "")
    total   = len(docs)

    # Enrich
    for doc in docs:
        doc["_title"] = clean_title(doc)
        doc["_tag"]   = reclassify(doc)   # 細化後的 tag

    slim = [
        {
            "url":         d["url"],
            "title":       d["_title"],
            "scraped_at":  d.get("scraped_at", "")[:10],
            "tag":         d["_tag"],
            "orig_tag":    d.get("tag", "other"),
            "type":        d.get("type", ""),
            "output_file": d.get("output_file", ""),
        }
        for d in docs
    ]
    docs_js = json.dumps(slim, ensure_ascii=False)

    # 分類統計（細化後）
    tag_counts: dict[str, int] = {}
    for d in slim:
        tag_counts[d["tag"]] = tag_counts.get(d["tag"], 0) + 1

    # Section HTML
    sections_html = ""
    for tag in TAG_ORDER:
        if tag not in tag_counts:
            continue
        icon, label, desc, color = TAG_META.get(tag, ("📄", tag, "", "#555"))
        count = tag_counts[tag]
        sections_html += f"""
  <div class="cat-section" data-cat="{tag}">
    <div class="cat-header" style="--accent:{color}">
      <h2 class="cat-title">{icon} {label}</h2>
      <span class="cat-count" id="count-{tag}">{count}</span>
      <span class="cat-desc">{desc}</span>
    </div>
    <div class="card-grid" id="grid-{tag}"></div>
  </div>"""

    # 篩選按鈕
    filter_btns = '<button class="filter-btn active" data-cat="all">全部 <span class="btn-count">{total}</span></button>\n'.format(total=total)
    for tag in TAG_ORDER:
        if tag not in tag_counts:
            continue
        icon, label, _d, _c = TAG_META.get(tag, ("📄", tag, "", ""))
        cnt = tag_counts[tag]
        filter_btns += f'    <button class="filter-btn" data-cat="{tag}">{icon} {label} <span class="btn-count">{cnt}</span></button>\n'

    tags_js = json.dumps(TAG_ORDER)

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>銘傳大學 選課資訊 自動爬蟲</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;600;700&display=swap" rel="stylesheet"/>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ font-family: "Noto Sans TC","PingFang TC","Microsoft JhengHei",sans-serif;
           margin:0; padding:0; background:#f0f4f8; color:#2c3e50; min-height:100vh; }}

    /* ─ Header ─ */
    header {{ background: linear-gradient(135deg,#1a3c6e 0%,#2471a3 60%,#1abc9c 100%);
              color:white; padding:2rem 1.5rem 1.4rem; text-align:center; position:relative; overflow:hidden; }}
    header::before {{ content:''; position:absolute; inset:0;
                      background:url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.04'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E"); }}
    header h1 {{ margin:0 0 .4rem; font-size:1.8rem; font-weight:700; position:relative; }}
    header p  {{ margin:0; opacity:.85; font-size:.95rem; position:relative; }}
    .meta-chips {{ margin-top:.9rem; display:flex; gap:.5rem; flex-wrap:wrap; justify-content:center; position:relative; }}
    .chip {{ display:inline-flex; align-items:center; gap:.35rem;
             background:rgba(255,255,255,.15); border:1px solid rgba(255,255,255,.25);
             border-radius:999px; padding:.25rem .9rem; font-size:.8rem; }}
    .pulse {{ width:8px; height:8px; background:#2ecc71; border-radius:50%; flex-shrink:0;
              animation:pulse 1.8s ease-in-out infinite; }}
    @keyframes pulse {{ 0%,100%{{opacity:1;transform:scale(1)}} 50%{{opacity:.5;transform:scale(.8)}} }}

    /* ─ Sticky Controls ─ */
    .controls-wrap {{ position:sticky; top:0; z-index:100;
                      background:white; box-shadow:0 2px 8px rgba(0,0,0,.08); }}
    .controls {{ max-width:1100px; margin:0 auto; padding:.8rem 1rem; display:flex; gap:.7rem; flex-wrap:wrap; align-items:center; }}
    .search-wrap {{ flex:1 1 220px; position:relative; }}
    .search-wrap input {{ width:100%; padding:.55rem .9rem .55rem 2.4rem; border:1.5px solid #d0dbe8;
                          border-radius:8px; font-size:.9rem; outline:none; background:white;
                          color:#2c3e50; transition:border-color .15s,box-shadow .15s; font-family:inherit; }}
    .search-wrap input:focus {{ border-color:#2471a3; box-shadow:0 0 0 3px rgba(36,113,163,.12); }}
    .search-icon {{ position:absolute; left:.75rem; top:50%; transform:translateY(-50%);
                    color:#9ab; font-size:1rem; pointer-events:none; }}
    .filter-row {{ display:flex; gap:.4rem; flex-wrap:wrap; }}
    .filter-btn {{ padding:.38rem .85rem; border-radius:20px; border:1.5px solid #d0dbe8;
                   background:white; font-size:.8rem; cursor:pointer; color:#555;
                   transition:all .15s; user-select:none; font-family:inherit; }}
    .filter-btn:hover {{ border-color:#2471a3; color:#2471a3; }}
    .filter-btn.active {{ background:#2471a3; border-color:#2471a3; color:white; font-weight:700; }}
    .btn-count {{ background:rgba(255,255,255,.25); border-radius:99px; padding:.05rem .45rem; font-size:.72rem; margin-left:.2rem; }}
    .filter-btn:not(.active) .btn-count {{ background:#e8f0fb; color:#2471a3; }}
    .type-btn {{ padding:.38rem .85rem; border-radius:20px; border:1.5px solid #d0dbe8;
                 background:white; font-size:.8rem; cursor:pointer; color:#555;
                 transition:all .15s; font-family:inherit; }}
    .type-btn.pdf.active  {{ background:#fde8e8; border-color:#c0392b; color:#c0392b; font-weight:700; }}
    .type-btn.web.active  {{ background:#e8f5e9; border-color:#2e7d32; color:#2e7d32; font-weight:700; }}

    /* ─ Results Bar ─ */
    .results-bar {{ max-width:1100px; margin:.6rem auto 0; padding:0 1rem;
                    font-size:.82rem; color:#789; }}

    /* ─ Main ─ */
    main {{ max-width:1100px; margin:.8rem auto 3rem; padding:0 1rem; }}
    .cat-section {{ margin-bottom:1.6rem; }}
    .cat-header {{ display:flex; align-items:center; gap:.55rem; margin-bottom:.65rem;
                   border-left:4px solid var(--accent,#2471a3); padding-left:.65rem; }}
    .cat-title  {{ font-size:1rem; font-weight:700; color:#1a3c6e; margin:0; }}
    .cat-count  {{ background:#e8f0fb; color:#2471a3; border-radius:999px;
                   padding:.1rem .55rem; font-size:.74rem; font-weight:700; }}
    .cat-desc   {{ font-size:.78rem; color:#9ab; margin-left:.2rem; }}

    /* ─ Cards ─ */
    .card-grid {{ display:grid; gap:.5rem; }}
    .card {{ background:white; border-radius:10px; box-shadow:0 1px 4px rgba(0,0,0,.07);
             padding:.75rem 1rem; display:grid;
             grid-template-columns:auto 1fr auto; gap:.4rem .85rem; align-items:start;
             transition:box-shadow .15s,transform .15s; }}
    .card:hover {{ box-shadow:0 4px 14px rgba(0,0,0,.11); transform:translateY(-1px); }}
    .card.hidden {{ display:none; }}
    .badge {{ display:inline-block; padding:.15rem .5rem; border-radius:4px;
              font-size:.7rem; font-weight:700; white-space:nowrap; margin-top:.15rem; }}
    .badge.pdf     {{ background:#fde8e8; color:#c0392b; }}
    .badge.webpage {{ background:#e8f5e9; color:#2e7d32; }}
    .badge.doc     {{ background:#e8f0fb; color:#2471a3; }}
    .card-body  {{ min-width:0; }}
    .card-title {{ font-size:.87rem; font-weight:600; color:#1a3c6e; margin:0 0 .22rem; line-height:1.45; }}
    .card-title a {{ color:inherit; text-decoration:none; }}
    .card-title a:hover {{ color:#2471a3; text-decoration:underline; }}
    .card-meta  {{ font-size:.74rem; color:#9ab; }}
    .card-meta a {{ color:#2471a3; text-decoration:none; }}
    .card-meta a:hover {{ text-decoration:underline; }}
    .card-actions {{ display:flex; flex-direction:column; align-items:flex-end; gap:.3rem; }}
    .btn-link {{ display:inline-block; padding:.24rem .65rem; border-radius:5px;
                 font-size:.74rem; text-decoration:none; white-space:nowrap; font-family:inherit; }}
    .btn-txt {{ background:#e8f0fb; color:#2471a3; }}
    .btn-txt:hover {{ background:#c8daef; }}
    .btn-src {{ background:#f0f4f8; color:#555; }}
    .btn-src:hover {{ background:#dde5ee; }}

    .empty {{ text-align:center; padding:3rem 1rem; color:#aaa; font-size:.95rem; display:none; }}
    .empty.show {{ display:block; }}
    footer {{ text-align:center; color:#9ab; font-size:.78rem; margin:0 0 2.5rem; padding:0 1rem; line-height:1.9; }}

    /* ─ Responsive ─ */
    @media(max-width:600px){{
      header h1 {{ font-size:1.35rem; }}
      .card {{ grid-template-columns:auto 1fr; }}
      .card-actions {{ flex-direction:row; flex-wrap:wrap; grid-column:1/-1; }}
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
      <input type="text" id="searchInput" placeholder="搜尋標題或來源網址…" autocomplete="off"/>
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

<script>
const DOCS = {docs_js};
const TAGS = {tags_js};

function getFileName(f) {{ return f.split('/').pop(); }}

function badgeClass(type) {{
  if (type === 'pdf') return 'pdf';
  if (type === 'webpage') return 'webpage';
  return 'doc';
}}
function badgeLabel(type) {{
  if (type === 'pdf') return 'PDF';
  if (type === 'webpage') return '網頁';
  return type.toUpperCase();
}}

function renderCards() {{
  TAGS.forEach(tag => {{
    const grid = document.getElementById('grid-' + tag);
    if (!grid) return;
    const items = DOCS.filter(d => d.tag === tag);
    grid.innerHTML = items.map(item => {{
      const fname = getFileName(item.output_file);
      const bc = badgeClass(item.type);
      const bl = badgeLabel(item.type);
      return `<div class="card" data-tag="${{item.tag}}" data-type="${{item.type}}" data-search="${{(item.title+' '+item.url).toLowerCase()}}">
        <div><span class="badge ${{bc}}">${{bl}}</span></div>
        <div class="card-body">
          <p class="card-title"><a href="${{fname}}">${{item.title}}</a></p>
          <span class="card-meta">爬取：${{item.scraped_at}} &nbsp;·&nbsp; <a href="${{item.url}}" target="_blank" rel="noopener">原始頁面 ↗</a></span>
        </div>
        <div class="card-actions">
          <a class="btn-link btn-txt" href="${{fname}}">📄 查看文字</a>
          <a class="btn-link btn-src" href="${{item.url}}" target="_blank" rel="noopener">🔗 原始連結</a>
        </div>
      </div>`;
    }}).join('');
  }});
}}

let activeCat='all', activeType=null, searchQ='';

function applyFilters() {{
  const cards = document.querySelectorAll('.card');
  let visible = 0;
  TAGS.forEach(tag => {{
    const sec = document.querySelector('.cat-section[data-cat="'+tag+'"]');
    if (sec) sec.style.display = (activeCat==='all'||activeCat===tag) ? '' : 'none';
  }});
  cards.forEach(card => {{
    const ok = (activeCat==='all' || activeCat===card.dataset.tag)
            && (!activeType || card.dataset.type===activeType)
            && (!searchQ   || card.dataset.search.includes(searchQ));
    card.classList.toggle('hidden', !ok);
    if (ok) visible++;
  }});
  TAGS.forEach(tag => {{
    const el = document.getElementById('count-'+tag);
    if (el) el.textContent = document.querySelectorAll('.cat-section[data-cat="'+tag+'"] .card:not(.hidden)').length;
  }});
  document.getElementById('resultsBar').textContent = `顯示 ${{visible}} / ${{DOCS.length}} 筆`;
  document.getElementById('emptyState').classList.toggle('show', visible===0);
}}

document.querySelectorAll('.filter-btn').forEach(btn => btn.addEventListener('click', () => {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  activeCat = btn.dataset.cat;
  applyFilters();
}}));

document.querySelectorAll('.type-btn').forEach(btn => btn.addEventListener('click', () => {{
  if (btn.classList.contains('active')) {{ btn.classList.remove('active'); activeType=null; }}
  else {{
    document.querySelectorAll('.type-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active'); activeType = btn.dataset.type;
  }}
  applyFilters();
}}));

document.getElementById('searchInput').addEventListener('input', e => {{
  searchQ = e.target.value.trim().toLowerCase();
  applyFilters();
}});

renderCards();
applyFilters();
</script>
</body>
</html>"""

    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"✅ docs/index.html 已產生（{total} 份文件，細化分類 + 篩選 + 搜尋）")


if __name__ == "__main__":
    build()
