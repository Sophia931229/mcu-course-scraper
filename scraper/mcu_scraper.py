"""
銘傳大學選課資訊爬蟲 v3.1
- 文章內容直接嵌入 index.json 的 content 欄位
- 不依賴 .txt 檔案連結，Pages 上直接 modal 展開
"""

import re
import json
import time
import hashlib
import logging
import requests
import pdfplumber
import docx
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("scraper.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

TARGET_PAGES = [
    {"name": "教務處最新公告",  "url": "https://academic.mcu.edu.tw/",         "tag": "announcement"},
    {"name": "教務處公告列表",  "url": "https://academic.mcu.edu.tw/?cat=2",    "tag": "announcement"},
    {"name": "新生選課注意事項","url": "https://freshman.mcu.edu.tw/a01/a01-04/","tag": "freshman"},
    {"name": "英語教學中心選課","url": "https://elc.mcu.edu.tw/%E9%81%B8%E8%AA%B2/","tag": "english"},
    {"name": "開課與師資資訊",  "url": "https://academic.mcu.edu.tw/coursestructure/","tag": "course_structure"},
]

COURSE_KEYWORDS = [
    "選課","course","課程","開課","停課","加退選",
    "選課辦法","選課時間","選課注意","課表","學分",
    "暑修","補修","重修","校際","網路選課","停班",
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

TAG_LABELS = {
    "announcement":     "📢 教務處公告",
    "add_drop":         "🔄 加退選公告",
    "cross_school":     "🏫 校際選課",
    "ai_alliance":      "🤖 AI 聯盟課程",
    "double_major":     "🎓 輔系雙主修",
    "remedial":         "📝 暑修補修重修",
    "class_change":     "⚠️ 停課調課補課",
    "freshman":         "🌱 新生選課說明",
    "english":          "🌐 英語教學中心",
    "course_structure": "📚 開課與課程架構",
    "other":            "📄 其他",
}


def detect_semester(text: str) -> str:
    m = re.search(r"(\d{3,4})學年度?第?(\d)學期", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return ""

def refine_tag(tag: str, title: str, url: str) -> str:
    if tag != "announcement":
        return tag
    text = (title + " " + url).lower()
    for pattern, new_tag in RECLASSIFY_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            return new_tag
    return tag

def safe_get(url: str, timeout: int = 20):
    for attempt in range(3):
        try:
            resp = SESSION.get(url, timeout=timeout, allow_redirects=True)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            log.warning(f"[嘗試 {attempt+1}/3] 無法取得 {url}: {e}")
            time.sleep(2 ** attempt)
    return None

def url_to_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]

def is_course_related(text: str) -> bool:
    return any(kw in text.lower() for kw in COURSE_KEYWORDS)

def extract_text_from_pdf(pdf_bytes: bytes, slug: str) -> str:
    tmp = OUTPUT_DIR / f"_tmp_{slug}.pdf"
    tmp.write_bytes(pdf_bytes)
    parts = []
    try:
        with pdfplumber.open(str(tmp)) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                t = page.extract_text() or ""
                if t.strip():
                    parts.append(f"--- 第 {i} 頁 ---\n{t}")
        return "\n\n".join(parts)
    except Exception as e:
        return f"[無法解析 PDF: {e}]"
    finally:
        tmp.unlink(missing_ok=True)

def extract_text_from_docx(docx_bytes: bytes) -> str:
    import io
    try:
        d = docx.Document(io.BytesIO(docx_bytes))
        rows = [p.text for p in d.paragraphs if p.text.strip()]
        for table in d.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    rows.append(" | ".join(cells))
        return "\n".join(rows)
    except Exception as e:
        return f"[無法解析 DOCX: {e}]"

def extract_page_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script","style","nav","footer","header","aside"]):
        tag.decompose()
    main = (
        soup.find("main") or soup.find("article")
        or soup.find("div", class_=re.compile(r"content|main|post|entry", re.I))
        or soup.find("div", id=re.compile(r"content|main|post|entry", re.I))
        or soup.body
    )
    if not main:
        return soup.get_text(separator="\n", strip=True)
    lines = []
    for elem in main.descendants:
        if elem.name in ("h1","h2","h3","h4"):
            lines.append(f"\n## {elem.get_text(strip=True)}")
        elif elem.name in ("p","li","td","th"):
            t = elem.get_text(strip=True)
            if t:
                lines.append(t)
    return "\n".join(lines)

def find_relevant_links(soup: BeautifulSoup, base_url: str) -> list[tuple[str,str]]:
    seen, result = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(strip=True)
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.scheme not in ("http","https") or full in seen:
            continue
        seen.add(full)
        ext = parsed.path.lower().split(".")[-1]
        if ext in ("pdf","doc","docx"):
            result.append((full, text or href))
        elif "mcu.edu.tw" in parsed.netloc and (is_course_related(text) or is_course_related(href)):
            result.append((full, text or href))
    return result

def make_record(url, title, tag, doc_type, content, semester="") -> dict:
    return {
        "id":         url_to_id(url),
        "url":        url,
        "title":      title,
        "scraped_at": datetime.now().isoformat(),
        "tag":        refine_tag(tag, title, url),
        "type":       doc_type,
        "semester":   semester or detect_semester(title + " " + url),
        "content":    content[:8000],   # 限制單筆最大 8000 字元
    }

def scrape_page(page_cfg: dict) -> list[dict]:
    url, tag, name = page_cfg["url"], page_cfg["tag"], page_cfg["name"]
    log.info(f"▶ 爬取: {name} ({url})")
    resp = safe_get(url)
    if not resp:
        return []

    soup = BeautifulSoup(resp.content, "lxml")
    results = []

    text = extract_page_text(soup)
    if text.strip():
        results.append(make_record(url, name, tag, "webpage", text))
        log.info(f"  ✓ 頁面 [{results[-1]['tag']}]")

    for link_url, link_text in find_relevant_links(soup, url):
        ext = urlparse(link_url).path.lower().split(".")[-1]
        if ext in ("pdf","doc","docx"):
            r = download_doc(link_url, link_text, tag)
            if r:
                results.append(r)
        elif is_course_related(link_text):
            r = scrape_subpage(link_url, link_text, tag)
            if r:
                results.append(r)

    return results

def download_doc(url: str, title: str, base_tag: str) -> dict | None:
    log.info(f"  ↳ 文件: {title[:40]}")
    resp = safe_get(url)
    if not resp:
        return None
    ext = urlparse(url).path.lower().split(".")[-1]
    if ext == "pdf":
        text = extract_text_from_pdf(resp.content, url_to_id(url))
    elif ext in ("doc","docx"):
        text = extract_text_from_docx(resp.content)
    else:
        return None
    if not text.strip():
        return None
    log.info(f"    ✓ [{ext}] {len(text)} 字元")
    return make_record(url, title, base_tag, ext, text)

def scrape_subpage(url: str, title: str, base_tag: str) -> dict | None:
    log.info(f"  ↳ 子頁面: {title[:40]}")
    resp = safe_get(url)
    if not resp:
        return None
    soup = BeautifulSoup(resp.content, "lxml")
    text = extract_page_text(soup)
    if not text.strip():
        return None
    # 附加子頁面內的文件
    extras = []
    for link_url, link_text in find_relevant_links(soup, url):
        ext = urlparse(link_url).path.lower().split(".")[-1]
        if ext in ("pdf","doc","docx"):
            r = safe_get(link_url)
            if r:
                doc_text = (extract_text_from_pdf(r.content, url_to_id(link_url))
                            if ext == "pdf"
                            else extract_text_from_docx(r.content))
                if doc_text.strip():
                    extras.append(f"\n\n[附件: {link_text}]\n{doc_text[:2000]}")
    log.info(f"    ✓ 子頁面 [{refine_tag(base_tag, title, url)}]")
    return make_record(url, title, base_tag, "webpage", text + "".join(extras))

def generate_index(all_results: list[dict]) -> None:
    now = datetime.now().isoformat()
    # 去重
    seen: dict[str, dict] = {}
    for r in all_results:
        u = r["url"]
        if u not in seen or r["scraped_at"] > seen[u]["scraped_at"]:
            seen[u] = r
    deduped = list(seen.values())

    tag_counts: dict[str, int] = {}
    for r in deduped:
        tag_counts[r["tag"]] = tag_counts.get(r["tag"], 0) + 1

    data = {
        "generated_at":    now,
        "total_documents": len(deduped),
        "tag_counts":      tag_counts,
        "documents":       deduped,
    }
    out = OUTPUT_DIR / "index.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"✅ index.json 已產生（{len(deduped)} 筆，含內文）")
    for t, c in sorted(tag_counts.items(), key=lambda x: -x[1]):
        log.info(f"   {TAG_LABELS.get(t, t)}: {c} 筆")

def main():
    log.info("=" * 60)
    log.info("銘傳大學選課資訊爬蟲 v3.1 啟動")
    log.info(f"時間: {datetime.now().isoformat()}")
    log.info("=" * 60)
    all_results = []
    for cfg in TARGET_PAGES:
        try:
            all_results.extend(scrape_page(cfg))
        except Exception as e:
            log.error(f"爬取 {cfg['name']} 時發生錯誤: {e}", exc_info=True)
        time.sleep(1)
    generate_index(all_results)
    log.info(f"🎉 完成！共 {len(all_results)} 筆")

if __name__ == "__main__":
    main()
