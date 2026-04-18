"""Detailed PDF audit report generator using reportlab."""
from __future__ import annotations
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)

SEVERITY_COLORS = {
    "critical": colors.HexColor("#E63946"),
    "high": colors.HexColor("#F4A261"),
    "medium": colors.HexColor("#2A9D8F"),
    "low": colors.HexColor("#525252"),
}


def _rupees(v):
    try:
        f = float(v)
        return f"Rs {f:,.0f}"
    except Exception:
        return str(v) if v is not None else "-"


def build_report(session: dict, flags: list[dict], transactions: list[dict]) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title=f"PWD Audit Report - {session.get('division_name','')}",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=22,
                        textColor=colors.HexColor("#0A0A0A"), leading=26)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=14,
                        textColor=colors.HexColor("#1D3557"), leading=18)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8,
                           textColor=colors.HexColor("#525252"))
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9, leading=12)
    cover_sub = ParagraphStyle("cov", parent=styles["Normal"], fontSize=10,
                               textColor=colors.HexColor("#525252"))

    story = []

    # -------- Cover Page --------
    story.append(Spacer(1, 3 * cm))
    story.append(Paragraph("PWD Audit Red Flags Report", h1))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Automated forensic audit · BEAMS / AMS data", cover_sub))
    story.append(Spacer(1, 1.5 * cm))

    meta_data = [
        ["Division", session.get("division_name") or "-"],
        ["DDO Code", session.get("ddo_code") or "-"],
        ["Audit Period", session.get("audit_period") or "-"],
        ["Prepared by", session.get("auditor_name") or "-"],
        ["Session ID", session.get("id", "")],
        ["Generated", datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")],
        ["Files processed", str(len(session.get("files", [])) or session.get("file_count", 0))],
        ["Transactions parsed", str(len(transactions))],
        ["Total red flags", str(len(flags))],
    ]
    t = Table(meta_data, colWidths=[5 * cm, 14 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#525252")),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#0A0A0A")),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E5E5")),
    ]))
    story.append(t)
    story.append(PageBreak())

    # -------- Summary table --------
    story.append(Paragraph("Red Flag Summary by Severity", h2))
    story.append(Spacer(1, 0.3 * cm))

    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    rule_counts = {}
    for f in flags:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
        rule_counts[f["rule_code"]] = rule_counts.get(f["rule_code"], 0) + 1

    sev_data = [["Severity", "Count"]]
    for sev in ["critical", "high", "medium", "low"]:
        sev_data.append([sev.upper(), counts[sev]])
    tt = Table(sev_data, colWidths=[5 * cm, 3 * cm])
    tt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A0A0A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E5E5")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E5E5")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    for i, sev in enumerate(["critical", "high", "medium", "low"], start=1):
        tt.setStyle(TableStyle([("TEXTCOLOR", (0, i), (0, i), SEVERITY_COLORS[sev]),
                                ("FONTNAME", (0, i), (0, i), "Helvetica-Bold")]))
    story.append(tt)
    story.append(Spacer(1, 0.8 * cm))

    if rule_counts:
        story.append(Paragraph("By Rule", h2))
        story.append(Spacer(1, 0.2 * cm))
        r_data = [["Rule Code", "Flag Count"]]
        for rc, ct in sorted(rule_counts.items(), key=lambda x: -x[1]):
            r_data.append([rc, ct])
        rt = Table(r_data, colWidths=[7 * cm, 3 * cm])
        rt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A0A0A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E5E5")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E5E5")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(rt)

    story.append(PageBreak())

    # -------- Detailed flag listing --------
    story.append(Paragraph("Red Flags — Detailed Findings", h2))
    story.append(Spacer(1, 0.4 * cm))

    if not flags:
        story.append(Paragraph("No red flags were detected in this audit session.", body))
    for idx, f in enumerate(flags, 1):
        color = SEVERITY_COLORS.get(f["severity"], colors.black)
        sev_style = ParagraphStyle(f"sev_{idx}", parent=body, fontSize=8,
                                   textColor=color, fontName="Helvetica-Bold")
        header_tbl = Table([
            [Paragraph(f"<b>#{idx} · {f['rule_code']}</b> — {f['rule_title']}", body),
             Paragraph(f["severity"].upper(), sev_style)]
        ], colWidths=[22 * cm, 3 * cm])
        header_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FAFAFA")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E5E5")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ]))
        story.append(header_tbl)

        ref = f.get("transaction_ref", {})
        work_label = ref.get("work_name") or ref.get("work_id") or ref.get("voucher_no") or "-"
        detail = [
            ["Transaction", str(work_label)[:180]],
            ["Work / Voucher ID", ref.get("work_id") or ref.get("voucher_no") or "-"],
            ["Type", (ref.get("type") or "-").replace("_", " ").title()],
            ["Source File", ref.get("source_file") or "-"],
            ["Reason", f["reason"]],
            ["Evidence", ", ".join(f"{k}={_fmt_evidence(v)}" for k, v in f["evidence"].items())[:600]],
        ]
        dt = Table(detail, colWidths=[4 * cm, 21 * cm])
        dt.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#525252")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#F0F0F0")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E5E5")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(dt)
        story.append(Spacer(1, 0.4 * cm))

    doc.build(story)
    return buf.getvalue()


def _fmt_evidence(v):
    if isinstance(v, float):
        if abs(v) > 1000:
            return f"{v:,.2f}"
        return str(v)
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}:{_fmt_evidence(x)}" for k, x in v.items()) + "}"
    return str(v)
