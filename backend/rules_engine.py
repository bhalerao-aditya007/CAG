"""Deterministic rules engine - applies 17 PWD red flag rules to parsed transactions.

A red flag is a dict:
  rule_id, severity, transaction_id, evidence (dict), reason (str)
"""
from __future__ import annotations
import re
import uuid
from datetime import date, datetime, timedelta
from collections import defaultdict
from typing import Any

from rules_data import RULES_BY_ID


def _today() -> date:
    return datetime.utcnow().date()


def _parse_date(s: Any) -> date | None:
    if not s:
        return None
    if isinstance(s, date):
        return s
    try:
        return datetime.fromisoformat(str(s)).date()
    except Exception:
        return None


def _norm_remark(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def _make_flag(rule_id: str, tx: dict, evidence: dict, reason: str) -> dict:
    meta = RULES_BY_ID[rule_id]
    return {
        "id": str(uuid.uuid4()),
        "rule_id": rule_id,
        "rule_code": meta["code"],
        "rule_title": meta["title"],
        "severity": meta["severity"],
        "transaction_id": tx.get("_id"),
        "transaction_ref": {
            "type": tx.get("type"),
            "work_id": tx.get("work_id"),
            "voucher_no": tx.get("voucher_no"),
            "work_name": tx.get("work_name"),
            "source_file": tx.get("source_file"),
        },
        "evidence": evidence,
        "reason": reason,
    }


# -------- Individual rule checks --------
def check_r01_diversion(tx: dict):
    if tx.get("type") != "deposit_work":
        return None
    remark = _norm_remark(tx.get("remark"))
    work_name = _norm_remark(tx.get("work_name"))
    if not remark or not work_name:
        return None
    # If remark text doesn't share any significant token with work_name => diversion
    def tokens(s):
        return {w for w in re.findall(r"[a-z0-9]+", s) if len(w) > 3}
    common = tokens(remark) & tokens(work_name)
    if len(common) == 0:
        return _make_flag("R01", tx,
            {"remark": tx.get("remark"), "work_name": tx.get("work_name")},
            "Expenditure remark has no overlap with work name — indicates diversion of deposit funds to another work.")
    return None


def check_r02_wasteful_survey(tx: dict):
    if tx.get("type") != "capital_work":
        return None
    remark = _norm_remark(tx.get("remark"))
    if "survey" in remark:
        cum_exp = tx.get("cumulative_expenditure") or 0
        bill_amount = tx.get("bill_amount") or 0
        if (cum_exp and cum_exp > 0 and (bill_amount == 0 or bill_amount is None)) or remark.strip() in ("survey works", "survey work"):
            return _make_flag("R02", tx,
                {"remark": tx.get("remark"), "cumulative_expenditure": cum_exp, "bill_amount": bill_amount},
                "Expenditure booked under 'Survey Works' with no RA-bill payment for other items — wasteful survey expenditure.")
    return None


def check_r03_excess_no_approval(tx: dict):
    if tx.get("type") != "capital_work":
        return None
    aa = tx.get("aa_amount") or 0
    exp = tx.get("cumulative_expenditure") or 0
    if aa > 0 and exp > 0 and exp > aa * 1.10:
        pct = (exp - aa) / aa * 100
        return _make_flag("R03", tx,
            {"aa_amount": aa, "cumulative_expenditure": exp, "excess_percent": round(pct, 2)},
            f"Up-to-date expenditure (₹{exp:,.0f}) exceeds AA Amount (₹{aa:,.0f}) by {pct:.1f}% — requires Government approval.")
    return None


def check_r05_delay_completion(tx: dict):
    if tx.get("type") != "capital_work":
        return None
    stip = _parse_date(tx.get("stipulated_completion_date"))
    if not stip and tx.get("work_order_date") and tx.get("time_limit_months"):
        wo = _parse_date(tx.get("work_order_date"))
        if wo:
            stip = wo + timedelta(days=int(float(tx["time_limit_months"])) * 30)
    if stip and stip < _today():
        cum_exp = tx.get("cumulative_expenditure") or 0
        cc = tx.get("contract_cost") or 0
        # only flag if work is not fully paid (<95% complete)
        if cc == 0 or cum_exp < cc * 0.95:
            return _make_flag("R05", tx,
                {"stipulated_completion_date": stip.isoformat(), "today": _today().isoformat(),
                 "cumulative_expenditure": cum_exp, "contract_cost": cc},
                f"Work past stipulated completion date ({stip.isoformat()}) and not fully executed.")
    return None


def check_r07_no_centage(tx: dict):
    if tx.get("type") != "deposit_work":
        return None
    centage = tx.get("centage_amount")
    bill = tx.get("bill_amount") or tx.get("cumulative_expenditure") or 0
    if bill > 0 and (centage is None or centage == 0):
        return _make_flag("R07", tx,
            {"bill_amount": bill, "centage_amount": centage},
            f"Deposit work has bill/expenditure ₹{bill:,.0f} but Centage Amount is Nil — non-recovery of 5% centage charges.")
    return None


def check_r08_unspent_balance(tx: dict):
    if tx.get("type") != "deposit_work":
        return None
    balance = tx.get("balance_amount") or 0
    remark = _norm_remark(tx.get("remark"))
    if balance > 100000 and "work completed" in remark:
        return _make_flag("R08", tx,
            {"balance_amount": balance, "remark": tx.get("remark")},
            f"Work Completed but unspent balance ₹{balance:,.0f} (>₹1 lakh) with DDO — must be returned to user department.")
    return None


def check_r09_excess_25(tx: dict):
    if tx.get("type") != "capital_work":
        return None
    cc = tx.get("contract_cost") or 0
    exp = tx.get("cumulative_expenditure") or 0
    if cc > 0 and exp > cc * 1.25:
        pct = (exp - cc) / cc * 100
        return _make_flag("R09", tx,
            {"contract_cost": cc, "cumulative_expenditure": exp, "excess_percent": round(pct, 2)},
            f"Cumulative expenditure (₹{exp:,.0f}) exceeds contract cost (₹{cc:,.0f}) by {pct:.1f}% — violates Clause 38 (>25% variation).")
    return None


def check_r10_abandoned(tx: dict):
    if tx.get("type") != "capital_work":
        return None
    cc = tx.get("contract_cost") or 0
    exp = tx.get("cumulative_expenditure") or 0
    last_ra = _parse_date(tx.get("last_ra_bill_date")) or _parse_date(tx.get("ra_bill_payment_date"))
    if cc > 0 and last_ra and exp < cc * 0.75:
        three_yrs = _today() - timedelta(days=3 * 365)
        if last_ra < three_yrs:
            return _make_flag("R10", tx,
                {"contract_cost": cc, "cumulative_expenditure": exp,
                 "last_ra_bill_date": last_ra.isoformat(), "utilization_percent": round(exp / cc * 100, 1)},
                f"Only {exp / cc * 100:.1f}% of contract cost utilized and last RA bill paid on {last_ra.isoformat()} (>3 yrs ago) — indicates abandoned work.")
    return None


def check_r12_parking(tx: dict):
    if tx.get("type") != "capital_work":
        return None
    amount = tx.get("bill_amount") or 0
    remark = _norm_remark(tx.get("remark"))
    pay_date = _parse_date(tx.get("ra_bill_payment_date"))
    transfer_keywords = ("electric division", "other division", "transfer", "electrical division")
    if amount > 5000000 and pay_date and pay_date.month == 3 and any(k in remark for k in transfer_keywords):
        return _make_flag("R12", tx,
            {"amount": amount, "payment_date": pay_date.isoformat(), "remark": tx.get("remark")},
            f"Transfer of ₹{amount:,.0f} to another division in March ({pay_date.isoformat()}) — parking of fund at fag end of year.")
    return None


def check_r13_14_delay_penalty_bg(tx: dict):
    if tx.get("type") != "capital_work":
        return None
    stip = _parse_date(tx.get("stipulated_completion_date"))
    if not stip and tx.get("work_order_date") and tx.get("time_limit_months"):
        wo = _parse_date(tx.get("work_order_date"))
        if wo:
            stip = wo + timedelta(days=int(float(tx["time_limit_months"])) * 30)
    ra_date = _parse_date(tx.get("ra_bill_payment_date"))
    if stip and ra_date and ra_date > stip:
        flags = []
        flags.append(_make_flag("R13", tx,
            {"stipulated_completion_date": stip.isoformat(), "ra_bill_payment_date": ra_date.isoformat()},
            f"RA bill paid on {ra_date.isoformat()}, past stipulated completion {stip.isoformat()} — penalty for delay not imposed."))
        flags.append(_make_flag("R14", tx,
            {"stipulated_completion_date": stip.isoformat(), "ra_bill_payment_date": ra_date.isoformat()},
            f"RA bill paid on {ra_date.isoformat()}, past stipulated completion {stip.isoformat()} — Insurance Policy / Bank Guarantee likely lapsed."))
        return flags
    return None


def check_r16_hand_receipt(tx: dict):
    if tx.get("type") != "cashbook":
        return None
    amount = tx.get("bill_amount") or 0
    mode = _norm_remark(tx.get("payment_mode")) + " " + _norm_remark(tx.get("remark"))
    if amount > 1000000 and re.search(r"hand\s*receipt|\bhr\b|vide\s*h\.?r\.?", mode):
        return _make_flag("R16", tx,
            {"amount": amount, "voucher_no": tx.get("voucher_no"), "payment_mode": tx.get("payment_mode")},
            f"Voucher #{tx.get('voucher_no') or ''} paid ₹{amount:,.0f} via Hand Receipt — irregular payment for regular work.")
    return None


def check_r17_no_classification(tx: dict):
    if tx.get("type") != "cashbook":
        return None
    amount = tx.get("bill_amount") or 0
    head = str(tx.get("classification_head") or "").strip()
    if amount > 1000000 and not head:
        return _make_flag("R17", tx,
            {"amount": amount, "voucher_no": tx.get("voucher_no"), "classification_head": head},
            f"Voucher #{tx.get('voucher_no') or ''} paid ₹{amount:,.0f} without Major Head classification.")
    return None


# -------- Cross-transaction rules --------
def check_r04_overlapping(transactions: list[dict]) -> list[dict]:
    flags = []
    caps = [t for t in transactions if t.get("type") == "capital_work" and t.get("road_code")]
    buckets = defaultdict(list)
    for t in caps:
        buckets[t["road_code"]].append(t)
    for code, items in buckets.items():
        if len(items) < 2:
            continue
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                ak1, ak2 = a.get("km_start"), a.get("km_end")
                bk1, bk2 = b.get("km_start"), b.get("km_end")
                if None in (ak1, ak2, bk1, bk2):
                    continue
                # overlap check
                if min(ak2, bk2) > max(ak1, bk1):
                    flags.append(_make_flag("R04", a,
                        {"road_code": code,
                         "work_a": {"work_id": a.get("work_id"), "km": f"{ak1}-{ak2}"},
                         "work_b": {"work_id": b.get("work_id"), "km": f"{bk1}-{bk2}"}},
                        f"Overlapping work detected on {code}: {ak1}-{ak2} km vs {bk1}-{bk2} km (work {b.get('work_id')})."))
    return flags


def check_r06_splitting_contractor(transactions: list[dict]) -> list[dict]:
    flags = []
    agreements = [t for t in transactions if t.get("type") == "agreement" and t.get("contractor_name")]
    buckets = defaultdict(list)
    for t in agreements:
        key = (_norm_remark(t.get("contractor_name")), t.get("award_year") or "", t.get("road_code") or "")
        buckets[key].append(t)
    for key, items in buckets.items():
        if len(items) < 2:
            continue
        small = [t for t in items if (t.get("contract_cost") or 0) < 1000000 and (t.get("contract_cost") or 0) > 0]
        if len(small) >= 2:
            for t in small:
                flags.append(_make_flag("R06", t,
                    {"contractor": t.get("contractor_name"), "road_code": t.get("road_code"),
                     "year": t.get("award_year"), "sibling_count": len(small)},
                    f"{len(small)} works <₹10 lakh awarded to same contractor '{t.get('contractor_name')}' on {t.get('road_code')} in {t.get('award_year')} — splitting of work."))
    return flags


def check_r11_inflated_ssr(transactions: list[dict]) -> list[dict]:
    flags = []
    agreements = [t for t in transactions if t.get("type") == "agreement"]
    by_year = defaultdict(list)
    for t in agreements:
        yr = t.get("award_year") or "unknown"
        by_year[yr].append(t)
    for yr, items in by_year.items():
        if len(items) < 5:
            continue
        below = [t for t in items if (t.get("percent_above_below") or 0) <= -10]
        total_cost = sum((t.get("contract_cost") or 0) for t in items)
        below_cost = sum((t.get("contract_cost") or 0) for t in below)
        count_pct = len(below) / len(items) * 100
        cost_pct = (below_cost / total_cost * 100) if total_cost > 0 else 0
        if count_pct > 20 or cost_pct > 20:
            ref_tx = items[0]
            flags.append(_make_flag("R11", ref_tx,
                {"year": yr, "total_works": len(items), "below_10_count": len(below),
                 "count_pct": round(count_pct, 1), "cost_pct": round(cost_pct, 1),
                 "total_cost": total_cost, "below_cost": below_cost},
                f"Year {yr}: {len(below)}/{len(items)} works ({count_pct:.1f}%) below 10% tender OR below-cost share {cost_pct:.1f}% — inflated SSR/DSR."))
    return flags


def check_r15_split_higher(transactions: list[dict]) -> list[dict]:
    flags = []
    caps = [t for t in transactions if t.get("type") == "capital_work" and t.get("road_code")]
    buckets = defaultdict(list)
    for t in caps:
        buckets[t["road_code"]].append(t)
    for code, items in buckets.items():
        if len(items) < 2:
            continue
        pricey = [t for t in items if ((t.get("tech_sanction_cost") or t.get("contract_cost") or 0) > 10000000)]
        for i, a in enumerate(pricey):
            for b in pricey[i + 1:]:
                ak1, ak2 = a.get("km_start"), a.get("km_end")
                bk1, bk2 = b.get("km_start"), b.get("km_end")
                if None in (ak1, ak2, bk1, bk2):
                    continue
                # adjacent (endpoint touches within 1 km)
                if abs(ak2 - bk1) < 1 or abs(bk2 - ak1) < 1:
                    flags.append(_make_flag("R15", a,
                        {"road_code": code,
                         "work_a": {"work_id": a.get("work_id"), "km": f"{ak1}-{ak2}", "ts": a.get("tech_sanction_cost") or a.get("contract_cost")},
                         "work_b": {"work_id": b.get("work_id"), "km": f"{bk1}-{bk2}", "ts": b.get("tech_sanction_cost") or b.get("contract_cost")}},
                        f"Adjacent works on {code} (₹{a.get('tech_sanction_cost') or a.get('contract_cost'):,.0f} + ₹{b.get('tech_sanction_cost') or b.get('contract_cost'):,.0f}) — split to avoid higher-authority sanction."))
    return flags


# -------- Main entrypoint --------
PER_ROW_CHECKS = [
    check_r01_diversion, check_r02_wasteful_survey, check_r03_excess_no_approval,
    check_r05_delay_completion, check_r07_no_centage, check_r08_unspent_balance,
    check_r09_excess_25, check_r10_abandoned, check_r12_parking,
    check_r13_14_delay_penalty_bg, check_r16_hand_receipt, check_r17_no_classification,
]

CROSS_CHECKS = [check_r04_overlapping, check_r06_splitting_contractor,
                check_r11_inflated_ssr, check_r15_split_higher]


def evaluate(transactions: list[dict]) -> list[dict]:
    flags: list[dict] = []
    for tx in transactions:
        for check in PER_ROW_CHECKS:
            try:
                res = check(tx)
                if isinstance(res, list):
                    flags.extend(res)
                elif res:
                    flags.append(res)
            except Exception as e:
                # don't crash on one bad row
                continue
    for check in CROSS_CHECKS:
        try:
            flags.extend(check(transactions))
        except Exception:
            continue
    return flags
