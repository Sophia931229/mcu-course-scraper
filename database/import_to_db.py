"""
匯入腳本：把爬蟲 output/*.txt 存進 MySQL，依 mcu_scraper.py 的標籤分類
標籤對照：
  announcement   → 教務處公告
  freshman       → 新生選課說明
  english        → 英語教學中心
  course_structure → 開課與課程架構
  other          → 其他
用法：python import_to_db.py
"""

import mysql.connector
from pathlib import Path

# ── 設定（請修改這裡）────────────────────────────
MYSQL_CONFIG = {
    "host":     "localhost",
    "port":     3306,
    "user":     "root",
    "password": "你的MySQL密碼",
    "database": "mcu_courses",
}

OUTPUT_DIR = Path("../scraper/output")  # 爬蟲輸出資料夾
# ────────────────────────────────────────────────

# 與 mcu_scraper.py 的 tag 對應的中文名稱與說明
TAG_META = {
    "announcement":    {"label": "教務處公告",     "description": "教務處最新公告與選課相關通知"},
    "freshman":        {"label": "新生選課說明",   "description": "新生入學選課注意事項與流程說明"},
    "english":         {"label": "英語教學中心",   "description": "英語教學中心選課相關資訊"},
    "course_structure":{"label": "開課與課程架構", "description": "各系所課程規劃、學期課表與師資資訊"},
    "other":           {"label": "其他",           "description": "其他選課相關資訊"},
}


def get_conn():
    return mysql.connector.connect(**MYSQL_CONFIG)


def init_db(conn):
    cur = conn.cursor()

    cur.execute("CREATE DATABASE IF NOT EXISTS mcu_courses CHARACTER SET utf8mb4")
    cur.execute("USE mcu_courses")

    # 分類表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            tag         VARCHAR(50) UNIQUE NOT NULL,
            label       VARCHAR(100) NOT NULL,
            description VARCHAR(255),
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """)

    # 文件表（含 category_id 外鍵）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            category_id INT,
            title       VARCHAR(500),
            url         TEXT,
            tag         VARCHAR(50),
            file_type   VARCHAR(20),
            content     LONGTEXT,
            scraped_at  VARCHAR(50),
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY  uniq_url_title (url(255), title(200)),
            FOREIGN KEY (category_id) REFERENCES categories(id)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """)

    conn.commit()
    cur.close()
    print("✅ 資料表建立完成")


def seed_categories(conn) -> dict[str, int]:
    """把 TAG_META 寫進 categories 表，回傳 tag → id 對照"""
    cur = conn.cursor()
    tag_to_id = {}

    for tag, meta in TAG_META.items():
        cur.execute("""
            INSERT INTO categories (tag, label, description)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                label       = VALUES(label),
                description = VALUES(description)
        """, (tag, meta["label"], meta["description"]))
        conn.commit()

        cur.execute("SELECT id FROM categories WHERE tag = %s", (tag,))
        row = cur.fetchone()
        tag_to_id[tag] = row[0]

    cur.close()
    print(f"✅ 分類資料已寫入（{len(tag_to_id)} 種標籤）")
    return tag_to_id


def parse_txt_file(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    lines = raw.split("\n")
    meta = {}
    content_start = 0
    for i, line in enumerate(lines):
        if line.startswith("來源: "):
            meta["url"] = line[4:].strip()
        elif line.startswith("標題: "):
            meta["title"] = line[4:].strip()
        elif line.startswith("爬取時間: "):
            meta["scraped_at"] = line[6:].strip()
        elif line.startswith("標籤: "):
            meta["tag"] = line[4:].strip()
        elif line.startswith("類型: "):
            meta["file_type"] = line[4:].strip()
        elif "=" * 10 in line:
            content_start = i + 2
            break
    content = "\n".join(lines[content_start:]).strip()
    return {**meta, "content": content}


def insert_document(conn, doc: dict, tag_to_id: dict) -> bool:
    tag = doc.get("tag", "other")
    # 若 tag 不在已知清單內，歸入 other
    if tag not in tag_to_id:
        tag = "other"
    category_id = tag_to_id[tag]

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO documents (category_id, title, url, tag, file_type, content, scraped_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            category_id = VALUES(category_id),
            content     = VALUES(content),
            scraped_at  = VALUES(scraped_at)
    """, (
        category_id,
        doc.get("title", ""),
        doc.get("url", ""),
        tag,
        doc.get("file_type", "webpage"),
        doc.get("content", ""),
        doc.get("scraped_at", ""),
    ))
    conn.commit()
    is_new = cur.rowcount == 1
    cur.close()
    return is_new


def print_summary(conn):
    """印出各分類的文件數量"""
    cur = conn.cursor()
    cur.execute("""
        SELECT c.label, c.tag, COUNT(d.id) as cnt
        FROM categories c
        LEFT JOIN documents d ON d.category_id = c.id
        GROUP BY c.id
        ORDER BY c.id
    """)
    rows = cur.fetchall()
    cur.close()

    print("\n📊 各分類文件數量：")
    print(f"  {'分類':<16} {'標籤':<20} {'文件數':>6}")
    print("  " + "-" * 46)
    for label, tag, cnt in rows:
        print(f"  {label:<16} {tag:<20} {cnt:>6}")


def main():
    print("🚀 開始匯入資料到 MySQL")

    conn = get_conn()
    init_db(conn)
    tag_to_id = seed_categories(conn)

    txt_files = [f for f in OUTPUT_DIR.glob("*.txt") if f.stem != "index"]
    print(f"📂 找到 {len(txt_files)} 個文字檔\n")

    new_count = update_count = error_count = 0

    for i, path in enumerate(txt_files, 1):
        print(f"[{i}/{len(txt_files)}] {path.name}", end=" ... ")
        try:
            doc = parse_txt_file(path)
            is_new = insert_document(conn, doc, tag_to_id)
            if is_new:
                new_count += 1
                print(f"✅ 新增  [{doc.get('tag','?')}]")
            else:
                update_count += 1
                print(f"🔄 更新  [{doc.get('tag','?')}]")
        except Exception as e:
            error_count += 1
            print(f"❌ 錯誤: {e}")

    print(f"\n{'='*40}")
    print(f"✅ 新增：{new_count} 筆")
    print(f"🔄 更新：{update_count} 筆")
    print(f"❌ 失敗：{error_count} 筆")
    print(f"{'='*40}")

    print_summary(conn)
    conn.close()


if __name__ == "__main__":
    main()
