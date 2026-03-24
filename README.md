# IPC Extractor

一個基於 Python 的 IPC (International Patent Classification) 分類標籤提取工具。

## 功能特點
- **高效解析**：使用 PyMuPDF (fitz) 高效讀取 PDF 目次。
- **智能清洗**：自動處理 CJK 中文字元斷行空格，並移除頁碼參考。
- **多格式輸出**：支援匯出為 CSV 格式及適合 PostgreSQL `COPY` 指令的 TSV 格式。

## 安裝需求
請確保已安裝 Python 3.8+，並執行以下指令安裝依賴：
```bash
pip install -r requirements.txt
```

## 使用方法
1. 將待處理的 PDF 檔案放入 `./data` 資料夾。
2. 執行提取腳本：
   ```bash
   python extract_ipc.py
   ```
3. 解析結果將儲存於 `./output` 資料夾。
