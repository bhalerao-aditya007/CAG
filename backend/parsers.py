"""
Parsers for Excel, PDF and Word files that extract PWD audit transactions.
Strategy: read rows/tables from each file format and normalize into a unified
transaction schema. Users can upload any of these:
  - Capital Works Report (Excel / PDF UC export)
  - Deposit Works UC (Excel / PDF)
  - Agreement Register (Excel / Word)
  - Cash Book Form 10 (PDF / Excel)

A unified transaction is a dict with the following optional keys:
  type, work_id, voucher_no, work_name, contractor_name, contract_cost,
  aa_amount, tech_sanction_cost, cumulative_expenditure, bill_amount,
  centage_amount, balance_amount, remark, work_order_date, time_limit_months,
  stipulated_completion_date, last_ra_bill_date, ra_bill_payment_date,
  payment_mode, classification_head, percent_above_below, road_code,
  km_start, km_end, source_file, row_ref, award_year, division,
  ts_date, aa_date, receipt_date, cumulative_receipt_amount
"""
from __future__ import annotations
import re
from datetime import datetime, date
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd


# ---------------- helpers -----------------
def _norm_key(k: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(k or "").strip().lower()).strip("_")


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        try:
            f = float(v)
            if pd.isna(f):
                return None
            return f
        except Exception:
            return None
    s = str(v).strip()
    if not s or s.lower() in {"nil", "na", "n/a", "-"}:
        return None
    s = s.replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def _to_date(v: Any) -> str | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except Exception:
            continue
    m = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", s)
    if m:
        try:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 2000
            return date(y, mo, d).isoformat()
        except Exception:
            return None
    return None


FIELD_ALIASES = {
    "work_id": ["work_id", "budget_item_no", "budgeted_item_no", "budget_id", "deposit_id", "deposit_work_id", "id"],
    "voucher_no": ["voucher_no", "voucher_number", "vch_no", "vr_no"],
    "work_name": ["name_of_work", "work_name", "particulars_of_work", "name_of_the_work", "description_of_work", "particulars"],
    "contractor_name": ["contractor_name", "name_of_contractor", "contractor", "payee", "payee_name", "firm_name"],
    "contract_cost": ["contract_cost", "contract_amount", "agreement_cost", "agreement_amount", "tender_cost"],
    "aa_amount": ["aa_amount", "aa_cost", "administrative_approval", "administrative_approval_amount", "approved_cost", "aa"],
    "tech_sanction_cost": ["technical_sanction_cost", "tech_sanction_cost", "ts_cost", "tech_sanction"],
    "cumulative_expenditure": ["cumulative_expenditure", "up_to_date_expenditure", "upto_date_expenditure", "total_expenditure", "expenditure", "progressive_expenditure"],
    "bill_amount": ["bill_amount", "ra_bill_amount", "amount"],
    "centage_amount": ["centage_amount", "centage_charges", "centage"],
    "balance_amount": ["balance_amount", "balance_amount_with_ddo", "balance_with_ddo", "unspent_balance", "balance"],
    "remark": ["remark", "remarks", "particulars_remark", "note", "description"],
    "work_order_date": ["work_order_date", "date_of_work_order", "wo_date"],
    "time_limit_months": ["time_limit", "time_limit_months", "original_time_limit", "stipulated_period", "completion_period_months"],
    "stipulated_completion_date": ["stipulated_date_of_completion", "stipulated_completion_date", "scheduled_date_of_completion", "completion_date"],
    "last_ra_bill_date": ["last_ra_bill_date", "last_ra_bill"],
    "ra_bill_payment_date": ["ra_bill_payment_date", "date_of_ra_bill", "ra_bill_date", "payment_date", "date"],
    "payment_mode": ["payment_mode", "mode_of_payment", "mode", "paid_by"],
    "classification_head": ["classification_head", "classification", "head_of_account", "major_head"],
    "percent_above_below": ["percent_above_below", "above_below_percent", "above_below_", "percentage_above_below"],
    "road_code": ["road_code", "road_no", "mdr_no", "sh_no", "nh_no", "road_name"],
    "award_year": ["year", "award_year", "financial_year"],
    "division": ["division", "division_name", "ddo"],
    # New fields for R18, R19, R20
    "ts_date": ["ts_date", "technical_sanction_date", "date_of_ts", "ts_accorded_on", "date_of_technical_sanction"],
    "aa_date": ["aa_date", "administrative_approval_date", "date_of_aa", "aa_accorded_on", "date_of_administrative_approval"],
    "receipt_date": ["receipt_date", "date_of_receipt", "fund_received_date", "deposit_received_date", "receipt_of_fund_date"],
    "cumulative_receipt_amount": ["cumulative_receipt_amount", "total_receipt", "receipt_amount", "amount_received", "cumulative_receipt", "total_receipts"],
}


def _map_row(row: dict) -> dict:
    out: dict[str, Any] = {}
    normed = {_norm_key(k): v for k, v in row.items()}
    for canonical, aliases in FIELD_ALIASES.items():
        for a in aliases:
            if a in normed and normed[a] not in (None, ""):
                out[canonical] = normed[a]
                break
    out["_raw"] = {k: (v.isoformat() if isinstance(v, (datetime, date)) else v) for k, v in row.items() if pd.notna(v) if not isinstance(v, float) or not pd.isna(v)} if row else {}
    # normalize numeric / date fields
    for k in ("contract_cost", "aa_amount", "tech_sanction_cost", "cumulative_expenditure",
              "bill_amount", "centage_amount", "balance_amount", "percent_above_below",
              "time_limit_months", "cumulative_receipt_amount"):
        if k in out:
            out[k] = _to_float(out[k])
    for k in ("work_order_date", "stipulated_completion_date", "last_ra_bill_date",
              "ra_bill_payment_date", "ts_date", "aa_date", "receipt_date"):
        if k in out:
            out[k] = _to_date(out[k])
    # string fields - clean up
    for k in ("work_id", "voucher_no", "work_name", "contractor_name", "remark",
              "payment_mode", "classification_head", "road_code", "division", "award_year"):
        if k in out and out[k] is not None:
            out[k] = str(out[k]).strip()
    # extract road_code from work_name if absent
    if not out.get("road_code") and out.get("work_name"):
        m = re.search(r"(SH[-\s]?\d+|MDR[-\s]?\d+|NH[-\s]?\d+)", out["work_name"], re.IGNORECASE)
        if m:
            out["road_code"] = m.group(1).upper().replace(" ", "")
    # extract km range from work_name
    if out.get("work_name"):
        m = re.search(r"(?:Km\.?|km)\s*(\d+)[/\s.]*(\d+)?\s*(?:to|TO|-)\s*(\d+)[/\s.]*(\d+)?", out["work_name"])
        if m:
            try:
                out["km_start"] = float(f"{m.group(1)}.{m.group(2) or 0}")
                out["km_end"] = float(f"{m.group(3)}.{m.group(4) or 0}")
            except Exception:
                pass
    return out


# ---------------- Excel ----------------
def parse_excel(content: bytes, filename: str, declared_type: str | None = None) -> list[dict]:
    xls = pd.ExcelFile(BytesIO(content))
    rows: list[dict] = []
    for sheet in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=sheet, dtype=object)
        except Exception:
            continue
        if df.empty:
            continue
        df = df.dropna(how="all").reset_index(drop=True)
        header_idx = 0
        for i in range(min(5, len(df))):
            row_vals = [str(x) for x in df.iloc[i].tolist() if pd.notna(x)]
            letters = sum(1 for v in row_vals if re.search(r"[A-Za-z]", v))
            if letters >= 3:
                header_idx = i
                break
        if header_idx > 0:
            df.columns = df.iloc[header_idx].astype(str).tolist()
            df = df.iloc[header_idx + 1:].reset_index(drop=True)
        for _, r in df.iterrows():
            d = r.to_dict()
            if all((pd.isna(v) or str(v).strip() == "") for v in d.values()):
                continue
            mapped = _map_row(d)
            mapped["source_file"] = filename
            mapped["source_sheet"] = sheet
            mapped["type"] = declared_type or _guess_type(mapped)
            rows.append(mapped)
    return rows


# ---------------- PDF ----------------
def parse_pdf(content: bytes, filename: str, declared_type: str | None = None) -> list[dict]:
    import pdfplumber
    rows: list[dict] = []
    with pdfplumber.open(BytesIO(content)) as pdf:
        for pg_idx, page in enumerate(pdf.pages):
            tables = page.extract_tables() or []
            for t in tables:
                if not t or len(t) < 2:
                    continue
                header = [str(c or "").strip() for c in t[0]]
                for r in t[1:]:
                    if not r or all((c is None or str(c).strip() == "") for c in r):
                        continue
                    d = {header[i] if i < len(header) else f"col_{i}": (str(c).strip() if c is not None else "") for i, c in enumerate(r)}
                    mapped = _map_row(d)
                    mapped["source_file"] = filename
                    mapped["source_page"] = pg_idx + 1
                    mapped["type"] = declared_type or _guess_type(mapped)
                    rows.append(mapped)
            text = page.extract_text() or ""
            if "cash book" in text.lower() or "form 10" in text.lower() or "voucher" in text.lower():
                for line in text.split("\n"):
                    ml = re.search(r"voucher\s*(?:no\.?|number)?\s*[:\-]?\s*(\S+).*?([\d,]+\.?\d*)", line, re.IGNORECASE)
                    if ml:
                        amount = _to_float(ml.group(2))
                        if amount and amount > 50000:
                            payment_mode = "Hand Receipt" if re.search(r"\b(hand\s*receipt|vide\s*h\.?r\.?|paid\s*vide\s*hr)\b", line, re.IGNORECASE) else ""
                            rows.append({
                                "type": "cashbook",
                                "voucher_no": ml.group(1),
                                "bill_amount": amount,
                                "payment_mode": payment_mode,
                                "remark": line.strip()[:300],
                                "source_file": filename,
                                "source_page": pg_idx + 1,
                            })
    return rows


# ---------------- Word ----------------
def parse_docx(content: bytes, filename: str, declared_type: str | None = None) -> list[dict]:
    from docx import Document
    d = Document(BytesIO(content))
    rows: list[dict] = []
    for t_idx, table in enumerate(d.tables):
        if not table.rows:
            continue
        header = [c.text.strip() for c in table.rows[0].cells]
        for row in table.rows[1:]:
            cells = [c.text.strip() for c in row.cells]
            if all(not c for c in cells):
                continue
            rec = {header[i] if i < len(header) else f"col_{i}": cells[i] for i in range(len(cells))}
            mapped = _map_row(rec)
            mapped["source_file"] = filename
            mapped["source_table"] = t_idx + 1
            mapped["type"] = declared_type or _guess_type(mapped)
            rows.append(mapped)
    return rows


def _guess_type(mapped: dict) -> str:
    """Heuristic: classify row into capital_work, deposit_work, cashbook, or agreement."""
    src = (mapped.get("_raw") or {})
    joined = " ".join(str(v) for v in src.values()).lower()
    if mapped.get("voucher_no") or "cash book" in joined or "vide hr" in joined or "hand receipt" in joined:
        return "cashbook"
    if mapped.get("centage_amount") is not None or "deposit" in joined:
        return "deposit_work"
    if mapped.get("percent_above_below") is not None or mapped.get("contractor_name"):
        return "agreement"
    if mapped.get("contract_cost") or mapped.get("aa_amount") or mapped.get("cumulative_expenditure"):
        return "capital_work"
    return "capital_work"


def parse_file(content: bytes, filename: str, declared_type: str | None = None) -> list[dict]:
    ext = Path(filename).suffix.lower()
    if ext in (".xlsx", ".xls"):
        return parse_excel(content, filename, declared_type)
    if ext == ".pdf":
        return parse_pdf(content, filename, declared_type)
    if ext in (".docx", ".doc"):
        return parse_docx(content, filename, declared_type)
    raise ValueError(f"Unsupported file type: {ext}")
