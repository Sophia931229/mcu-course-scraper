# 🏫 銘傳大學選課資訊自動爬蟲

自動爬取銘傳大學（MCU）各官方網頁的選課相關公告，
支援 PDF / DOC / DOCX 轉文字，並透過 GitHub Actions 每日自動更新，結果 host 在 GitHub Pages。

---

## 🌐 線上瀏覽

> **GitHub Pages URL**（在你的 repo → Settings → Pages 啟用後）  
> `https://<你的帳號>.github.io/<repo名稱>/`

---

## 📦 功能

| 功能 | 說明 |
|------|------|
| 多來源爬取 | 教務處公告、新生選課說明、英語教學中心、課程架構等 |
| 文件轉換 | PDF → 純文字（pdfplumber）、DOC/DOCX → 純文字（python-docx）|
| 遞迴連結跟蹤 | 自動發現頁面中的選課相關連結與附件 |
| 自動排程 | GitHub Actions 每天 08:00 & 20:00（台灣時間）執行 |
| 手動觸發 | GitHub Actions → Run workflow 可立即執行 |
| 索引頁 | 自動產生 `docs/index.html`（GitHub Pages）與 `index.json` |

---

## 📁 專案結構

```
mcu-course-scraper/
├── .github/
│   └── workflows/
│       └── scrape.yml          # GitHub Actions 排程設定
├── scraper/
│   ├── mcu_scraper.py          # 主爬蟲程式
│   └── output/                 # 爬取結果（.txt 文字檔 + index）
│       ├── index.json
│       ├── index.md
│       └── *.txt
├── scripts/
│   └── build_html.py           # 產生 GitHub Pages 入口 HTML
├── docs/                       # GitHub Pages 靜態網站
│   ├── index.html
│   └── *.txt
├── requirements.txt
└── README.md
```

---

## 🚀 本地執行

```bash
# 1. 安裝相依套件
pip install -r requirements.txt

# 2. 執行爬蟲
cd scraper
python mcu_scraper.py

# 3. 建立 HTML 索引（選擇性）
cd ..
python scripts/build_html.py
```

---

## ☁️ 部署到 GitHub（逐步說明）

### Step 1 — 建立 Repository

1. 到 [github.com/new](https://github.com/new) 建立新 repo（例如 `mcu-course-scraper`）
2. 將本專案推上去：

```bash
git init
git add .
git commit -m "初始化：MCU 選課資訊爬蟲"
git remote add origin https://github.com/<你的帳號>/mcu-course-scraper.git
git branch -M main
git push -u origin main
```

### Step 2 — 啟用 GitHub Pages

1. 進入 repo → **Settings** → **Pages**
2. Source 選 **Deploy from a branch**
3. Branch 選 `main`，資料夾選 `/docs`
4. 儲存後等約 1 分鐘，你的網站就會在線了

### Step 3 — 讓 Actions 有寫入權限

1. 進入 repo → **Settings** → **Actions** → **General**
2. Workflow permissions 選 **Read and write permissions**
3. 儲存

### Step 4 — 手動執行一次

1. 進入 repo → **Actions** → **MCU Course Scraper**
2. 點 **Run workflow** → **Run workflow**

---

## ⚙️ 自訂爬取頻率

編輯 `.github/workflows/scrape.yml` 中的 `cron` 設定：

```yaml
schedule:
  - cron: "0 0 * * *"   # UTC 00:00 = 台灣 08:00
  - cron: "0 12 * * *"  # UTC 12:00 = 台灣 20:00
```

[Cron 語法產生器](https://crontab.guru/)

---

## 📋 爬取來源

| 來源 | URL |
|------|-----|
| 教務處首頁 | https://academic.mcu.edu.tw/ |
| 教務處公告 | https://academic.mcu.edu.tw/?cat=2 |
| 新生選課說明 | https://freshman.mcu.edu.tw/a01/a01-04/ |
| 英語教學中心 | https://elc.mcu.edu.tw/選課/ |
| 開課與師資 | https://academic.mcu.edu.tw/coursestructure/ |

---

## ⚠️ 注意事項

- 本工具僅用於彙整公開資訊，請遵守學校網站使用規範
- 請以各官方網站公告為準，本工具僅供參考
- 若學校網站結構更動，可能需要調整 `mcu_scraper.py` 中的爬取邏輯

---

## 📄 授權

MIT License
