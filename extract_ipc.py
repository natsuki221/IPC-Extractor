#!/usr/bin/env python3
"""
IPC 分類標籤提取工具 (優化版)
結合 PyMuPDF 高效能文本解析與高階中文字串清洗，
輸出為適合匯入 PostgreSQL 的 CSV 與 TSV 格式。

用法:
    python3 extract_ipc.py
    # 會自動批次讀取 ./data 下所有 PDF，並輸出到 ./output
"""

import re
import csv
import sys
from pathlib import Path
import pymupdf


class IPCDataExtractor:
    def __init__(self, include_main_class: bool = False):
        self.include_main_class = include_main_class

        # ── 正則表達式 ──────────────────────────────────────────────
        # 嚴格限制開頭為 A-H (IPC 部類範圍)，避免誤判其他英文縮寫
        self.sub_class_re = re.compile(r"^([A-H]\d{2,3}[A-Z]+)\s+(.+)")  # 次類，如 D01B
        self.main_class_re = re.compile(r"^([A-H]\d{2,3})\s+(.+)")  # 主類，如 D01

        # 通用頁碼參考：支援 A-H 所有部類 (例如 A-12, D_34, H-5)
        self.page_ref_re = re.compile(r"[.\s]*[A-H][_\-]\d+\s*$")

        # 頁眉頁尾與雜訊過濾 (利用正則過濾無效的換頁殘留物)
        self.noise_re = re.compile(r"^(目次|IPC 第.*版|本部內容|次部.*|\d+)$")

    def clean_description(self, text: str) -> str:
        """
        清洗描述文字：
        1. 移除結尾頁碼參考 (支援全分類)
        2. 移除 PDF 換行造成的中文斷字空格 (高階 CJK 處理)
        3. 壓縮連續空白
        """
        text = self.page_ref_re.sub("", text)

        # 處理中文字與中文字之間的空白（斷行殘留）
        text = re.sub(
            r"([\u4e00-\u9fff\uff00-\uffef，；、。：！？「」『』【】〔〕]) +([\u4e00-\u9fff\uff00-\uffef，；、。：！？「」『』【】〔〕A-Z（）])",
            r"\1\2",
            text,
        )
        # 執行第二次以處理連續中斷
        text = re.sub(
            r"([\u4e00-\u9fff\uff00-\uffef，；、。：！？「」『』【】〔〕]) +([\u4e00-\u9fff\uff00-\uffef，；、。：！？「」『』【】〔〕A-Z（）])",
            r"\1\2",
            text,
        )
        # 壓縮剩餘連續空白
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def extract_toc_text(self, pdf_path: Path) -> str:
        """使用 PyMuPDF 提取目次頁文字，並嚴格限制只讀取目次範圍"""
        toc_lines = []
        found_toc = False  # 標記是否已經進入目次區塊
        try:
            doc = pymupdf.open(pdf_path)
            for page in doc[:20]:
                text = page.get_text("text")

                # 嚴格界定：只處理明確包含「目次」字眼的頁面
                if "目次" in text:
                    found_toc = True
                    for line in text.splitlines():
                        line = line.strip()
                        if line and not self.noise_re.match(line):
                            toc_lines.append(line)
                else:
                    # 如果已經讀過目次頁，但下一頁卻沒有「目次」字眼，代表已經進入主文，立即強制中斷！
                    if found_toc:
                        break
        except Exception as e:
            print(f"[錯誤] 無法讀取 {pdf_path.name}: {e}", file=sys.stderr)

        return "\n".join(toc_lines)

    def parse_toc(self, raw_text: str) -> list[dict]:
        """狀態機解析：加入嚴格的中斷條件，防止狀態機暴走"""
        records = []
        current_label = None
        current_desc_parts = []

        def flush():
            if current_label:
                raw_desc = " ".join(current_desc_parts)
                desc = self.clean_description(raw_desc)
                if desc:
                    records.append({"ipc_label": current_label, "description": desc})

        for line in raw_text.splitlines():
            # 優先匹配次類
            m = self.sub_class_re.match(line)
            if m:
                flush()
                current_label = m.group(1)
                current_desc_parts = [m.group(2)]

                # 如果這行已經自帶頁碼 (代表單行就結束了)，立刻 Flush 並關閉狀態
                if self.page_ref_re.search(line):
                    flush()
                    current_label = None
                continue

            # 匹配主類 (若啟用)
            if self.include_main_class:
                m = self.main_class_re.match(line)
                if m:
                    flush()
                    current_label = m.group(1)
                    current_desc_parts = [m.group(2)]
                    continue

            # 延續前一標籤的描述
            if current_label:
                # 【防呆機制】：如果遇到主文特徵 (如 1/00, 19/21, 次類索引)，強制中斷當前收集
                if re.match(r"^(\d+/\d+|次類索引|附註)", line):
                    flush()
                    current_label = None
                    continue

                current_desc_parts.append(line)

                # 【煞車機制】：如果這行結尾是頁碼 (如 ..... D-2)，代表敘述結束，立刻 Flush
                if self.page_ref_re.search(line):
                    flush()
                    current_label = None

        flush()  # 儲存最後一筆
        return records

    def process_pdf(self, pdf_path: str) -> list[dict]:
        path = Path(pdf_path)
        if not path.exists():
            print(f"[警告] 找不到檔案：{pdf_path}", file=sys.stderr)
            return []

        print(f"[處理] {path.name} ...", file=sys.stderr)
        raw_text = self.extract_toc_text(path)
        records = self.parse_toc(raw_text)
        print(f"       → 解析出 {len(records)} 筆標籤", file=sys.stderr)
        return records


class Exporter:
    """處理不同資料庫或工具的匯出格式"""

    @staticmethod
    def write_csv(records: list[dict], output_path: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["ipc_label", "description"],
                quoting=csv.QUOTE_ALL,
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(records)

    @staticmethod
    def write_tsv_for_pg(records: list[dict], output_path: Path):
        """匯出適合 PostgreSQL COPY 的 TSV 格式"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            for r in records:
                label = r["ipc_label"].replace("\t", " ")
                desc = r["description"].replace("\t", " ").replace("\n", " ")
                f.write(f"{label}\t{desc}\n")


# ── 主程式 ──────────────────────────────────────────────────
def main():
    data_dir = Path("./data")
    output_dir = Path("./output")

    if not data_dir.exists() or not data_dir.is_dir():
        print(f"[錯誤] 找不到資料夾：{data_dir.absolute()}", file=sys.stderr)
        sys.exit(1)

    # 批次讀取 data 目錄下所有 PDF（含子目錄）
    pdf_files = sorted(
        [*data_dir.rglob("*.pdf"), *data_dir.rglob("*.PDF")],
        key=lambda p: str(p).lower(),
    )

    if not pdf_files:
        print(
            f"[錯誤] {data_dir.absolute()} 內沒有可處理的 PDF 檔案。", file=sys.stderr
        )
        sys.exit(1)

    print(
        f"[資訊] 在 {data_dir.absolute()} 找到 {len(pdf_files)} 個 PDF 檔案",
        file=sys.stderr,
    )

    extractor = IPCDataExtractor(include_main_class=False)
    all_records = []

    for pdf_path in pdf_files:
        all_records.extend(extractor.process_pdf(str(pdf_path)))

    if not all_records:
        print("[錯誤] 未解析到任何資料，請確認 PDF 內容或路徑。", file=sys.stderr)
        sys.exit(1)

    # 去重機制 (以 ipc_label 為 key)
    seen = {r["ipc_label"]: r for r in all_records}
    deduped = list(seen.values())
    deduped.sort(key=lambda x: x["ipc_label"])

    print(f"\n[完成] 共 {len(deduped)} 筆 (去重後)", file=sys.stderr)

    # 定義輸出路徑
    csv_out = output_dir / "ipc_subclasses.csv"
    tsv_out = output_dir / "ipc_subclasses.tsv"

    Exporter.write_csv(deduped, csv_out)
    print(f"[輸出] CSV → {csv_out.absolute()}", file=sys.stderr)

    Exporter.write_tsv_for_pg(deduped, tsv_out)
    print(f"[輸出] TSV → {tsv_out.absolute()}", file=sys.stderr)

    print("\n── 預覽前 5 筆 ──", file=sys.stderr)
    for r in deduped[:5]:
        print(f"  {r['ipc_label']:<8} | {r['description'][:60]}...", file=sys.stderr)


if __name__ == "__main__":
    main()
