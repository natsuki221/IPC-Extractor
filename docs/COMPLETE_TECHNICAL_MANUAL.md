# IPC Extractor 技術手冊

## 專案概述
本工具旨在從 IPC 分類階層的 PDF 檔案中自動提取「次類」(Sub-class) 標籤及其對應的敘述內容。

## 核心技術實現

### 1. 文本提取 (Text Extraction)
使用 `PyMuPDF` (pymupdf) 庫進行 PDF 內容讀取。
- **範疇限制**：腳本僅掃描 PDF 前 20 頁中包含「目次」關鍵字的頁面，以提高效能並減少雜訊。
- **早期中斷**：一旦偵測到離開目次區塊（進入主文或索引），立即停止解析。

### 2. 資料清洗 (Data Cleaning)
針對 PDF 轉換常遇到的問題進行優化：
- **CJK 斷行處理**：利用正則表達式偵測中文字元間的冗餘空格（由 PDF 換行引起）並予以消除。
- **頁碼過濾**：識別並移除結尾處如 `A-12` 或 `D_34` 等分類參考頁碼。

### 3. 解析邏輯 (Parsing Logic)
採用狀態機 (State Machine) 模式：
- 識別 A-H 部類的次類標籤 (如 `A01B`)。
- 收集跨行敘述文字直至遇到下一標籤或結束旗標。

## 資料格式

### CSV 輸出
- **路徑**: `output/ipc_subclasses.csv`
- **欄位**: `ipc_label`, `description`
- **特性**: 包含 BOM (UTF-8-SIG) 以利 Excel 直接開啟。

### PostgreSQL TSV 輸出
- **路徑**: `output/ipc_subclasses.tsv`
- **欄位**: `ipc_label`, `description` (以 Tab 分隔)
- **特性**: 移除 Tab 與換行符號，適合 `COPY` 指令快速匯入。

## 維護與擴充
若需支援「主類」(Main-class)，可於 `IPCDataExtractor` 初始化時將 `include_main_class` 設為 `True`。
