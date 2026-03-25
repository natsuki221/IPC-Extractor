# IPC Extractor

一個基於 Python 的 **IPC (International Patent Classification) 分類標籤提取工具**，能從 IPC 分類階層 PDF 檔案中自動擷取次類 (Sub-class) 標籤及對應描述，並輸出為 CSV / TSV 格式。

## 功能特點

| 功能 | 說明 |
|:-----|:-----|
| 🔍 **精準目次解析** | 依「目次-N」頁首標記自動定位並擷取目次頁，僅掃描前 20 頁即完成，避免進入主文區域 |
| ⚙️ **狀態機解析引擎** | 嚴格的正則表達式搭配狀態機，正確辨識 `A01B`–`H99Z` 格式的次類標籤，防止誤抓描述中的交叉引用 |
| 🧹 **智能文字清洗** | 雙重頁碼清洗策略（字母-數字型 / 點線+數字型）；自動移除 CJK 中文字元間因 PDF 折行產生的多餘空格 |
| 📦 **批次處理** | 自動掃描 `./data` 資料夾下所有 PDF，以標籤排序並去除重複 |
| 📄 **多格式輸出** | CSV（含 BOM，Excel 可直接開啟）與 PostgreSQL `COPY` 相容的 TSV |
| 🔧 **可擴充設計** | 初始化時設定 `include_main_class=True` 即可額外擷取主類 (Main-class) 標籤 |

## 專案結構

```
IPC-Extractor/
├── extract_ipc.py       # 核心提取腳本
├── requirements.txt     # Python 依賴
├── data/                # 放置待處理的 IPC PDF 檔案
├── output/              # 產出的 CSV / TSV 結果
│   ├── ipc_subclasses.csv
│   └── ipc_subclasses.tsv
├── docs/
│   └── COMPLETE_TECHNICAL_MANUAL.md  # 完整技術手冊
├── CHANGELOG.md
└── README.md
```

> [!NOTE]
> `data/` 與 `output/` 的內容透過 `.gitignore` 排除追蹤，僅以 `.gitkeep` 保留資料夾結構。

## 安裝需求

- Python 3.8+
- [PyMuPDF](https://pymupdf.readthedocs.io/)

```bash
pip install -r requirements.txt
```

## 使用方法

### 快速開始

1. 將 IPC 分類 PDF 檔案放入 `./data` 資料夾。
2. 執行提取腳本：
   ```bash
   python extract_ipc.py
   ```
3. 腳本會自動：
   - 掃描 `./data` 內所有 PDF 檔案
   - 從每份 PDF 的目次區段提取次類標籤與描述
   - 依標籤排序並去除重複項
   - 輸出至 `./output` 資料夾

### 執行範例

```
[資訊] 找到 8 個 PDF 檔案
[處理] A.pdf ...
       → 解析出 82 筆標籤
[處理] B.pdf ...
       → 解析出 65 筆標籤
...

[完成] 共 631 筆（去重後）
[輸出] CSV → .../output/ipc_subclasses.csv
[輸出] TSV → .../output/ipc_subclasses.tsv

── 預覽前 5 筆 ──
  A01B     | 一般之土壤處理（特用之機具、或用於特別耕作之裝置A01C...
  A01C     | 種植；播種；施肥
  A01D     | 收穫；割草
  A01F     | 穀物之脫粒；乾草或類似物之壓捆...
  A01G     | 園藝；蔬菜、花卉、稻、果樹、酒、啤酒花或海草之栽培...
```

## 輸出格式

### CSV (`output/ipc_subclasses.csv`)

- 編碼：UTF-8 with BOM（`utf-8-sig`），Excel 可直接開啟不亂碼
- 欄位以雙引號包覆，逗號分隔

```csv
"ipc_label","description"
"A01B","一般之土壤處理"
"A01C","種植；播種；施肥"
```

### TSV (`output/ipc_subclasses.tsv`)

- 編碼：UTF-8（無 BOM）
- Tab 鍵分隔，適合 PostgreSQL `COPY` 指令直接匯入

```sql
COPY ipc_subclasses (ipc_label, description)
FROM '/path/to/ipc_subclasses.tsv';
```

## 核心架構

### `IPCDataExtractor`

主要的擷取類別，負責：

1. **`extract_toc_text(pdf_path)`** — 使用 PyMuPDF 讀取 PDF，定位目次頁面並提取原始文字
2. **`parse_toc(raw_text)`** — 狀態機解析器，透過嚴格的正則表達式逐行辨識標籤與描述
3. **`clean_description(text)`** — 清洗描述文字：移除頁碼參考、修復 CJK 斷行空格、壓縮連續空白
4. **`process_pdf(pdf_path)`** — 整合以上流程的主入口

### `Exporter`

靜態工具類別，提供：

- **`write_csv()`** — 匯出 CSV 格式（含 BOM）
- **`write_tsv_for_pg()`** — 匯出 PostgreSQL 相容的 TSV 格式

## 技術文件

完整的技術說明與實作細節請參閱 [`docs/COMPLETE_TECHNICAL_MANUAL.md`](docs/COMPLETE_TECHNICAL_MANUAL.md)。

## 版本紀錄

詳見 [`CHANGELOG.md`](CHANGELOG.md)。

## 授權條款

此專案為私有專案，未附授權條款。
