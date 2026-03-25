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

        # 【修正 1】嚴格 IPC 標籤格式：
        #   次類  A-H + 2位數 + 1個大寫字母，如 D01B, G21H, D99Z
        #   主類  A-H + 2位數，              如 D01, G21, G99
        #
        # 關鍵改動：標籤之後只允許「行尾」或「2個以上空白 + 描述」，
        # 禁止 1 個空白後接數字、或標點後緊接文字。
        # 這樣可防止誤抓描述中的交叉引用，如：
        #   H01J，H05G 1/00；...  → 0 空白後接 ，  → 不匹配 ✓
        #   H04N 9/00；...        → 1 空白後接數字 → 不匹配 ✓
        #   G06T；類比...         → 0 空白後接 ；  → 不匹配 ✓
        #   G02B  光學元件...     → 2 空白後接中文 → 匹配   ✓
        #   G01B  (行尾)          → 0 字符          → 匹配   ✓
        self.sub_class_re = re.compile(
            r"^([A-H]\d{2}[A-Z])(?:\s*$|\s{2,}(.*))"
        )
        self.main_class_re = re.compile(
            r"^([A-H]\d{2})(?:\s*$|\s{2,}(.*))"
        )

        # 目次頁識別：PyMuPDF 讀取時「目次-N」出現在頁首
        self.toc_header_re = re.compile(r"目次-\d+")

        # 【修正 2】雙重頁碼清洗策略
        #
        # 策略 A：適用 D 部格式「...... D-9」（字母-數字）
        self.page_ref_letter_re = re.compile(r"[\s.]*[A-H][_\-]\d+\s*$")
        #
        # 策略 B：適用 G 部等格式「......... 20」（點線 + 純數字）
        # 匹配：2 個以上連續點、可選空白、可選版本注記 [n]、數字、行尾
        self.page_ref_dots_re = re.compile(
            r"\.{2,}[\s.]*(?:\[[\d,\s]+\]\s*)?\d+\s*$"
        )
        #
        # 策略 C：「[版本注記] 頁碼」獨行，如「[2] 120」
        # 用於 noise_re 過濾，防止混入描述
        self.citation_page_re = re.compile(r"^\[[\d,\s]+\]\s+\d+\s*$")

        # 雜訊行過濾（用於 extract_toc_text）
        self.noise_re = re.compile(
            r"^("
            r"目次-?\d*"             # 目次頁眉，如「目次-1」
            r"|IPC 第.*版"
            r"|本部內容"
            r"|次部[：:].*"          # 次部分隔標題
            r"|（參見與附註省略）"
            r"|\d+"                  # 純數字行（獨立頁碼）
            r")$"
        )

        # 主文特徵：遇到這些代表已進入內文，強制中斷狀態機
        # 注意：不納入 \d+/\d+，因 TOC 描述中的交叉引用（如 G01D 5/00；）
        # 可能折行至行首，不應被誤判為主文條目。
        # TOC 頁範圍已由 toc_header_re 嚴格限制，此處只需防邊界極端情況。
        self.content_break_re = re.compile(
            r"^("
            r"次類索引"
            r"|附註"
            r"|[A-H]-\d+"            # 內文頁碼如 D-2, G-1
            r")"
        )

    def clean_description(self, text: str) -> str:
        """
        清洗描述文字（依序執行）：
        1. 移除 D 部格式尾端頁碼（...... D-9）
        2. 移除 G 部格式尾端頁碼（......... 20 或 [2,5]........ 16）
        3. 移除 CJK 字符之間因 PDF 折行造成的空格
        4. 壓縮連續空白
        """
        # 策略 A：字母-數字型頁碼
        text = self.page_ref_letter_re.sub("", text)
        # 策略 B：點線+數字型頁碼
        text = self.page_ref_dots_re.sub("", text)

        # 移除 CJK 字符間的空格（PDF 折行殘留）
        CJK = r"[\u4e00-\u9fff\uff00-\uffef，；、。：！？「」『』【】〔〕]"
        CJK_R = r"[\u4e00-\u9fff\uff00-\uffef，；、。：！？「」『』【】〔〕A-Z（）]"
        text = re.sub(rf"({CJK}) +({CJK_R})", r"\1\2", text)
        text = re.sub(rf"({CJK}) +({CJK_R})", r"\1\2", text)

        # 壓縮剩餘連續空白
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def extract_toc_text(self, pdf_path: Path) -> str:
        """
        使用 PyMuPDF 提取目次頁文字，嚴格只讀取目次範圍。
        以頁首是否出現「目次-N」判斷是否為目次頁，離開後立即停止。
        """
        toc_lines = []
        found_toc = False

        try:
            doc = pymupdf.open(pdf_path)
            for page in doc[:20]:
                text = page.get_text("text")

                if self.toc_header_re.search(text):
                    found_toc = True
                    for line in text.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        # 過濾：標準雜訊行
                        if self.noise_re.match(line):
                            continue
                        # 【修正 3】過濾：「[版本] 頁碼」獨行，如「[2] 120」
                        if self.citation_page_re.match(line):
                            continue
                        toc_lines.append(line)
                else:
                    if found_toc:
                        break

        except Exception as e:
            print(f"[錯誤] 無法讀取 {pdf_path.name}: {e}", file=sys.stderr)

        return "\n".join(toc_lines)

    def parse_toc(self, raw_text: str) -> list[dict]:
        """
        狀態機解析目次文字。

        修正重點：
        - sub_class_re / main_class_re 更嚴格，避免誤抓描述中的交叉引用
        - 標籤獨行（描述為空）：下一行作為描述的起始
        - 標籤+描述同行（2+空格分隔）：直接作為描述
        - 「煞車」：行尾含頁碼時立刻 flush
        - 「防呆」：遇主文特徵強制中斷
        """
        records = []
        current_label = None
        current_desc_parts = []

        def flush():
            if current_label:
                raw_desc = " ".join(current_desc_parts)
                desc = self.clean_description(raw_desc)
                if desc:
                    records.append({"ipc_label": current_label, "description": desc})

        def has_page_ref(line: str) -> bool:
            """判斷此行尾端是否包含頁碼（煞車用）"""
            return bool(
                self.page_ref_letter_re.search(line)
                or self.page_ref_dots_re.search(line)
            )

        for line in raw_text.splitlines():
            line = line.strip()
            if not line:
                continue

            # ── 優先嘗試次類（格式較長），再嘗試主類 ──────────────
            matched = False

            m = self.sub_class_re.match(line)
            if m:
                flush()
                current_label = m.group(1)
                # group(2) 有值 → 標籤與描述同行（2+空白分隔）
                # group(2) 無值 → 標籤獨行，描述在下一行
                desc_part = (m.group(2) or "").strip()
                current_desc_parts = [desc_part] if desc_part else []
                # 若此行尾端已含頁碼，描述已完整，立刻結束
                if desc_part and has_page_ref(line):
                    flush()
                    current_label = None
                matched = True

            if not matched and self.include_main_class:
                m = self.main_class_re.match(line)
                if m:
                    flush()
                    current_label = m.group(1)
                    desc_part = (m.group(2) or "").strip()
                    current_desc_parts = [desc_part] if desc_part else []
                    matched = True

            # ── 延續前一標籤的描述 ──────────────────────────────────
            if not matched and current_label:
                # 防呆：遇主文特徵行，強制中斷
                if self.content_break_re.match(line):
                    flush()
                    current_label = None
                    continue

                current_desc_parts.append(line)

                # 煞車：此行結尾是頁碼，描述完整，立刻 flush
                if has_page_ref(line):
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

    pdf_files = sorted(
        [*data_dir.rglob("*.pdf"), *data_dir.rglob("*.PDF")],
        key=lambda p: str(p).lower(),
    )

    if not pdf_files:
        print(f"[錯誤] {data_dir.absolute()} 內沒有可處理的 PDF。", file=sys.stderr)
        sys.exit(1)

    print(
        f"[資訊] 找到 {len(pdf_files)} 個 PDF 檔案", file=sys.stderr
    )

    extractor = IPCDataExtractor(include_main_class=False)
    all_records = []
    for pdf_path in pdf_files:
        all_records.extend(extractor.process_pdf(str(pdf_path)))

    if not all_records:
        print("[錯誤] 未解析到任何資料。", file=sys.stderr)
        sys.exit(1)

    # 去重（保留第一筆，即最先出現的 PDF / 頁面）
    seen: dict[str, dict] = {}
    for r in all_records:
        if r["ipc_label"] not in seen:
            seen[r["ipc_label"]] = r
    deduped = sorted(seen.values(), key=lambda x: x["ipc_label"])

    print(f"\n[完成] 共 {len(deduped)} 筆（去重後）", file=sys.stderr)

    csv_out = output_dir / "ipc_subclasses.csv"
    tsv_out = output_dir / "ipc_subclasses.tsv"

    Exporter.write_csv(deduped, csv_out)
    print(f"[輸出] CSV → {csv_out.absolute()}", file=sys.stderr)
    Exporter.write_tsv_for_pg(deduped, tsv_out)
    print(f"[輸出] TSV → {tsv_out.absolute()}", file=sys.stderr)

    print("\n── 預覽前 5 筆 ──", file=sys.stderr)
    for r in deduped[:5]:
        desc = r["description"]
        suffix = "..." if len(desc) > 60 else ""
        print(f"  {r['ipc_label']:<8} | {desc[:60]}{suffix}", file=sys.stderr)


if __name__ == "__main__":
    main()