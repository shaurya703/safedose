"""Parse CDSCO 'Not of Standard Quality' (NSQ) monthly alert PDFs.

CDSCO publishes these as PDFs with a table per page. The columns (since the
2024 format) are:

    S.No | Product/Drug Name | Batch No. | Manufacturing Date | Expiry Date |
    Manufactured By | NSQ Result | Reported by CDSCO Laboratory

Older/var formats sometimes add a trailing column flagging spurious drugs.
This parser is tolerant: it locates the header row, maps columns by fuzzy
name, and pulls every data row (rows whose first cell is a serial number).

Run as a script to ingest a PDF into normalized JSON:

    python -m app.parser data/raw/NSQ_Alert_March-2025.pdf --period 2025-03 \
        --source-url https://cdsco.gov.in/.../NSQ%20Alert...March-2025.pdf
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Optional

import pdfplumber

from .schemas import FailureCategory

# --- column resolution -------------------------------------------------------

_COLUMN_ALIASES = {
    "sno": ["s.no", "s. no", "sno", "sl.no", "sl no", "s no"],
    "drug": ["product/drug name", "drug name", "name of drug", "product name", "drug"],
    "batch": ["batch no", "batch no.", "b.no", "batch", "batch number"],
    "mfg": ["manufacturing date", "mfg date", "mfg. date", "mfg"],
    "expiry": ["expiry date", "exp date", "exp. date", "expiry"],
    "maker": ["manufactured by", "name of manufacturer", "manufacturer", "mfd by"],
    "result": ["nsq result", "result", "nature of contravention", "reason"],
    "lab": ["reported by cdsco laboratory", "tested by", "name of laboratory", "lab"],
    "spurious": ["whether spurious", "spurious", "drugs declared spurious"],
}


def _norm_header(cell: str) -> str:
    return re.sub(r"\s+", " ", (cell or "").strip().lower())


def _resolve_columns(header: list[str]) -> dict[str, int]:
    cleaned = [_norm_header(h) for h in header]
    mapping: dict[str, int] = {}
    for key, aliases in _COLUMN_ALIASES.items():
        for i, h in enumerate(cleaned):
            if any(h == a or h.startswith(a) for a in aliases):
                mapping[key] = i
                break
    return mapping


# --- failure classification --------------------------------------------------

_CATEGORY_RULES: list[tuple[FailureCategory, list[str]]] = [
    (FailureCategory.spurious, ["spurious", "counterfeit", "fake", "not genuine"]),
    (FailureCategory.contamination, [
        "particulate", "microbial", "sterility", "bacterial", "endotoxin",
        "contamin", "fungal", "foreign matter",
    ]),
    (FailureCategory.dissolution, ["dissolution", "disintegration", "release"]),
    (FailureCategory.assay, ["assay", "content of", "potency", "drug content"]),
    (FailureCategory.labelling, ["label", "misbrand", "misleading", "declaration"]),
    (FailureCategory.physical, [
        "appearance", "ph", "uniformity of weight", "uniformity of content",
        "clarity", "colour", "color", "moisture", "loss on drying", "hardness",
    ]),
]


def classify_failure(reason: str) -> FailureCategory:
    low = (reason or "").lower()
    for category, keywords in _CATEGORY_RULES:
        if any(k in low for k in keywords):
            return category
    return FailureCategory.other


def normalize_batch(batch: str) -> str:
    """Batch numbers vary in punctuation/spacing across labels and the alert.

    Uppercase and strip everything that isn't alphanumeric so 'AD-204',
    'ad 204' and 'AD204' all compare equal.
    """
    return re.sub(r"[^A-Z0-9]", "", (batch or "").upper())


def _clean(cell: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (cell or "").replace("\n", " ")).strip()


@dataclass
class ParsedRow:
    drug_name: str
    batch_no: str
    manufacturer: str
    mfg_date: str
    expiry_date: str
    failure_reason: str
    tested_by: str
    is_spurious: bool


def parse_pdf(path: str) -> list[ParsedRow]:
    rows: list[ParsedRow] = []
    with pdfplumber.open(path) as pdf:
        mapping: dict[str, int] = {}
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table:
                    continue
                # (Re)resolve columns whenever a header row appears; tables
                # repeat the header on each page.
                header_idx = _find_header(table)
                if header_idx is not None:
                    mapping = _resolve_columns(table[header_idx])
                    body = table[header_idx + 1:]
                else:
                    body = table
                if "drug" not in mapping or "batch" not in mapping:
                    continue
                for r in body:
                    if not _is_data_row(r):
                        continue
                    rows.append(_row_from(r, mapping))
    return rows


def _find_header(table: list[list[str]]) -> Optional[int]:
    for i, row in enumerate(table[:3]):
        joined = " ".join(_norm_header(c) for c in row)
        if "batch" in joined and ("drug" in joined or "product" in joined):
            return i
    return None


def _is_data_row(row: list[str]) -> bool:
    if not row or not row[0]:
        return False
    first = row[0].strip().rstrip(".")
    return first.isdigit()


def _row_from(row: list[str], m: dict[str, int]) -> ParsedRow:
    def get(key: str) -> str:
        idx = m.get(key)
        return _clean(row[idx]) if idx is not None and idx < len(row) else ""

    reason = get("result")
    spurious_cell = get("spurious").lower()
    is_spurious = (
        "spurious" in reason.lower()
        or spurious_cell in {"yes", "y", "spurious", "true"}
    )
    return ParsedRow(
        drug_name=get("drug"),
        batch_no=get("batch"),
        manufacturer=get("maker"),
        mfg_date=get("mfg"),
        expiry_date=get("expiry"),
        failure_reason=reason,
        tested_by=get("lab"),
        is_spurious=is_spurious,
    )


def record_id(source_period: str, batch: str, drug: str) -> str:
    raw = f"{source_period}|{normalize_batch(batch)}|{drug.lower().strip()}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def to_records(
    parsed: list[ParsedRow], period: str, source_alert: str, source_url: str
) -> list[dict]:
    out = []
    for p in parsed:
        out.append({
            "id": record_id(period, p.batch_no, p.drug_name),
            "drug_name": p.drug_name,
            "batch_no": p.batch_no,
            "batch_no_normalized": normalize_batch(p.batch_no),
            "manufacturer": p.manufacturer or None,
            "mfg_date": p.mfg_date or None,
            "expiry_date": p.expiry_date or None,
            "failure_reason": p.failure_reason,
            "failure_category": classify_failure(p.failure_reason).value,
            "is_spurious": p.is_spurious,
            "tested_by": p.tested_by or None,
            "source_alert": source_alert,
            "source_url": source_url,
            "alert_period": period,
        })
    return out


def main() -> int:
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Parse a CDSCO NSQ alert PDF to JSON")
    ap.add_argument("pdf")
    ap.add_argument("--period", required=True, help="YYYY-MM of the alert")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    parsed = parse_pdf(args.pdf)
    alert = f"NSQ Alert {args.period}"
    records = to_records(parsed, args.period, alert, args.source_url)
    text = json.dumps(records, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
        print(f"wrote {len(records)} records -> {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
