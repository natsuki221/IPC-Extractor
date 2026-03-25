# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-03-25

### Added
- 大幅擴充 `README.md` 目錄，新增功能特點表格、專案結構樹、執行範例與輸出格式說明。

### Changed
- `extract_ipc.py`: 優化正則嚴格度，新增點線頁碼清洗，強化「目次-N」偵測與主文邊界控制。
- `docs/COMPLETE_TECHNICAL_MANUAL.md`: 更新提取邏輯與資料清洗策略說明。

## [1.0.0] - 2026-03-24

### Added
- 初始化專案結構。
- `extract_ipc.py`: 基於 PyMuPDF 的 IPC 分類標籤提取核心邏輯。
- 支援批次 PDF 處理、中文字串清洗與 CSV/TSV 匯出。
- 專案說明文檔 (README.md) 與技術手冊。
