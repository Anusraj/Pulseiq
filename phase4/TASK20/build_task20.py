"""Build the Task 20 board deck as a self-contained HTML deck and PDF."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Iterable

import duckdb
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DATABASE = ROOT / "pulseiq.duckdb"


def query(connection: duckdb.DuckDBPyConnection, statement: str) -> list[tuple]:
    return connection.execute(statement).fetchall()


def load_board_data() -> dict:
    connection = duckdb.connect(str(DATABASE), read_only=True)
    try:
        headcount = query(
            connection,
            """
            SELECT period_start::VARCHAR, SUM(metric_value)
            FROM metrics.m01_headcount
            GROUP BY 1 ORDER BY 1 DESC LIMIT 12
            """,
        )[::-1]
        attrition = query(
            connection,
            """
            SELECT period_start::VARCHAR,
                   100 * SUM(numerator) / NULLIF(SUM(denominator), 0)
            FROM metrics.m04_attrition_rate_monthly
            GROUP BY 1 ORDER BY 1 DESC LIMIT 6
            """,
        )[::-1]
        payroll = query(
            connection,
            """
            SELECT period_start::VARCHAR, SUM(metric_value)
            FROM metrics.m09_employer_payroll_cost
            GROUP BY 1 ORDER BY 1 DESC LIMIT 6
            """,
        )[::-1]
        dso = query(
            connection,
            """
            SELECT period_start::VARCHAR, metric_value
            FROM metrics.m20_days_sales_outstanding
            ORDER BY period_start DESC LIMIT 1
            """,
        )
        overdue = query(
            connection,
            """
            SELECT breakdown_id, metric_value
            FROM metrics.m21_overdue_receivables
            WHERE period_start = (SELECT MAX(period_start) FROM metrics.m21_overdue_receivables)
            ORDER BY metric_value DESC LIMIT 5
            """,
        )
        teams = query(
            connection,
            """
            SELECT breakdown_id, metric_value
            FROM metrics.m22_task_completion_rate
            WHERE period_start = (SELECT MAX(period_start) FROM metrics.m22_task_completion_rate)
            ORDER BY metric_value
            """,
        )
        profit = query(
            connection,
            """
            SELECT period_start::VARCHAR, metric_value
            FROM metrics.m17_net_profit ORDER BY period_start DESC LIMIT 1
            """,
        )
    finally:
        connection.close()
    return {
        "headcount": headcount,
        "attrition": attrition,
        "payroll": payroll,
        "dso": dso,
        "overdue": overdue,
        "teams": teams,
        "profit": profit,
        "checks": json.loads((OUT / "release_checks.json").read_text(encoding="utf-8")),
    }


def scale_points(values: Iterable[float], width: int, height: int, pad: int = 20) -> list[tuple[float, float]]:
    numbers = [float(value) for value in values]
    low, high = min(numbers), max(numbers)
    span = high - low or 1
    step = (width - 2 * pad) / max(1, len(numbers) - 1)
    return [
        (pad + index * step, height - pad - ((value - low) / span) * (height - 2 * pad))
        for index, value in enumerate(numbers)
    ]


def svg_line(values: list[float], labels: list[str], color: str = "#0B7285") -> str:
    width, height = 720, 210
    points = scale_points(values, width, height)
    path = " ".join(
        ("M" if index == 0 else "L") + f"{x:.1f},{y:.1f}"
        for index, (x, y) in enumerate(points)
    )
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}"/>' for x, y in points)
    xlabels = "".join(
        f'<text x="{x:.1f}" y="202" text-anchor="middle">{html.escape(label[-7:])}</text>'
        for (x, _), label in zip(points, labels)
    )
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img">'
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="4"/>'
        f"{dots}{xlabels}</svg>"
    )


def svg_bars(labels: list[str], values: list[float], color: str = "#0B7285") -> str:
    width, height = 720, 210
    maximum = max(values) or 1
    bar_width = (width - 40) / max(1, len(values)) - 8
    bars = []
    for index, (label, value) in enumerate(zip(labels, values)):
        x = 20 + index * (bar_width + 8)
        bar_height = (value / maximum) * 145
        y = 170 - bar_height
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" '
            f'fill="{color}" rx="4"/><text x="{x + bar_width / 2:.1f}" y="{y - 6:.1f}" '
            f'text-anchor="middle">{value:.1f}</text><text x="{x + bar_width / 2:.1f}" y="196" '
            f'text-anchor="middle">{html.escape(label)}</text>'
        )
    return f'<svg viewBox="0 0 {width} {height}" role="img">{"".join(bars)}</svg>'


def slide(number: int, title: str, finding: str, chart: str, recommendation: str, evidence: str) -> str:
    return f"""
    <section class="slide">
      <div class="slide-number">{number:02d} / 09</div>
      <h1>{html.escape(title)}</h1>
      <p class="finding">{html.escape(finding)}</p>
      <div class="chart">{chart}</div>
      <div class="recommendation"><strong>Recommendation</strong><br>{html.escape(recommendation)}</div>
      <p class="evidence">Evidence: {html.escape(evidence)}</p>
    </section>
    """


def build_html(data: dict) -> str:
    checks = data["checks"]
    headcount = data["headcount"]
    attrition = data["attrition"]
    payroll = data["payroll"]
    teams = data["teams"]
    start_count, end_count = float(headcount[0][1]), float(headcount[-1][1])
    growth = 100 * (end_count - start_count) / start_count
    team_labels = [str(row[0]).split("/")[0] for row in teams]
    team_values = [float(row[1]) for row in teams]
    dso_value = float(data["dso"][0][1])
    overdue_top = float(data["overdue"][0][1])
    payroll_latest = float(payroll[-1][1])
    attrition_latest = float(attrition[-1][1])
    slides = [
        slide(
            1,
            "PulseIQ board handover",
            "The product is decision-ready for workforce and cash monitoring, but cost action remains gated by one live reconciliation failure.",
            f'<div class="status-grid"><div><b>People</b><span>{end_count:,.0f} headcount</span></div><div><b>Cash</b><span>{dso_value:.0f} DSO days</span></div><div><b>Data trust</b><span class="amber">{checks["status"]}</span></div></div>',
            "Approve the operating cadence and fund the June payroll-ledger reconciliation before using cost metrics for a decision.",
            "Task 20 release checks and the governed metric views.",
        ),
        slide(
            2,
            "Finding 1 — workforce is scaling",
            f"Headcount increased from {start_count:,.0f} to {end_count:,.0f} in the latest 12-month view (+{growth:.1f}%).",
            svg_line([float(row[1]) for row in headcount], [str(row[0]) for row in headcount]),
            "Plan hiring capacity and manager span before growth creates an execution bottleneck.",
            "metrics.m01_headcount, October 2025–September 2026.",
        ),
        slide(
            3,
            "Finding 2 — attrition is manageable, not ignorable",
            f"Monthly attrition was {attrition_latest:.2f}% in September; the latest rolling view is the right board lens because monthly rates are noisy.",
            svg_line([float(row[1]) for row in attrition], [str(row[0]) for row in attrition], "#C4813C"),
            "Track rolling attrition by department and investigate persistent movement, not one-month spikes.",
            "metrics.m04_attrition_rate_monthly and M05 rolling attrition definition.",
        ),
        slide(
            4,
            "Finding 3 — payroll cost is material and not yet decision-safe",
            f"September employer payroll cost is INR {payroll_latest / 1_000_000:.1f}M; June has a critical INR 18,450 payroll-to-ledger mismatch.",
            svg_line([float(row[1]) / 1_000_000 for row in payroll], [str(row[0]) for row in payroll], "#C0392B"),
            "Do not approve a cost intervention from this metric until Finance closes DQ-C01 and documents the cause.",
            "metrics.m09_employer_payroll_cost and DQ-C01 in dq_results.csv.",
        ),
        slide(
            5,
            "Finding 4 — cash is tied up for 48 days",
            f"DSO is {dso_value:.0f} days; the largest overdue client balance is INR {overdue_top / 1_000_000:.1f}M.",
            svg_bars(
                [str(row[0]) for row in data["overdue"][:5]],
                [float(row[1]) / 1_000_000 for row in data["overdue"][:5]],
                "#C4813C",
            ),
            "Assign an owner and collection plan to the largest overdue account, with a weekly cash review until DSO improves.",
            "metrics.m20_days_sales_outstanding and M21 overdue receivables.",
        ),
        slide(
            6,
            "Finding 5 — delivery performance has a visible team spread",
            f"Latest sprint completion ranges from {team_values[0]:.1f}% to {team_values[-1]:.1f}% across reportable teams.",
            svg_bars(team_labels, team_values, "#0B7285"),
            "Pair the lowest reportable team with the strongest team to share planning and flow practices; do not rank teams on velocity alone.",
            "metrics.m22_task_completion_rate, sprint SP-38; groups below five are suppressed.",
        ),
        slide(
            7,
            "What is trusted now",
            "Warehouse reconciliation and metric privacy validation pass; the DQ gate is conditional because one critical check fails.",
            '<div class="check-grid"><div class="pass">WAREHOUSE<br><b>PASS</b></div><div class="pass">METRIC VIEWS<br><b>PASS</b></div><div class="amber-box">LIVE DQ<br><b>CONDITIONAL</b></div></div>',
            "Release the dashboard and API for governed monitoring, but label cost metrics with the reconciliation caveat.",
            "release_checks.json; warehouse_reconciliation.csv; metric_view_validation.csv.",
        ),
        slide(
            8,
            "30 / 60 / 90-day decisions",
            "The next actions are operational: close the data issue, focus cash ownership, then improve workforce and team planning.",
            '<div class="timeline"><div><b>30 days</b><span>Close DQ-C01; assign overdue owner.</span></div><div><b>60 days</b><span>Review rolling attrition by department.</span></div><div><b>90 days</b><span>Re-plan capacity and share delivery practices.</span></div></div>',
            "Make the data-quality owner accountable for the first action and return to the board with a clean reconciliation.",
            "Task 20 final handover recommendation.",
        ),
        slide(
            9,
            "Handover decision",
            "PulseIQ is released as a trusted governed monitoring product with one explicit hold: no cost decision until June payroll reconciles to the ledger.",
            '<div class="final-callout">USE NOW<br><b>People, cash, team monitoring</b><br><br>HOLD<br><b>Cost intervention decisions</b></div>',
            "Accept the handover, use the live dashboard/API, and schedule the DQ-C01 closure review before the next board pack.",
            "RELEASE_NOTES.md, final_handover.md, and demo_script.md.",
        ),
    ]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>PulseIQ board handover</title>
<style>
body{{margin:0;background:#e9eef2;color:#173d38;font-family:Arial,sans-serif}}
.deck{{max-width:1180px;margin:0 auto}} .slide{{min-height:680px;background:#fff;margin:28px 0;padding:52px 72px;box-sizing:border-box;box-shadow:0 6px 24px #173d3820;position:relative}}
.slide-number{{color:#0b7285;font-size:13px;font-weight:bold;letter-spacing:2px}} h1{{font-size:37px;margin:18px 0;color:#173d38}} .finding{{font-size:23px;line-height:1.35;max-width:950px;color:#405b59}}
.chart{{margin:24px 0;height:220px}} svg{{width:100%;height:100%;font-size:12px;fill:#526563}} .recommendation{{background:#eef7f5;border-left:5px solid #0b7285;padding:16px 20px;font-size:18px;line-height:1.4;max-width:900px}} .evidence{{font-size:13px;color:#71817f;margin-top:22px}}
.status-grid,.check-grid,.timeline{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin:50px 0}} .status-grid div,.check-grid div,.timeline div{{border:1px solid #d5e0de;border-radius:12px;padding:24px;font-size:19px}} .status-grid span,.timeline span{{display:block;font-size:28px;margin-top:12px}} .pass{{background:#eaf7f0;color:#16704a}} .amber,.amber-box{{color:#a45d15}} .amber-box{{background:#fff5e8;border:1px solid #f0d7b2!important}} .timeline div{{background:#f5faf9}} .timeline b{{font-size:22px}} .timeline span{{font-size:17px;line-height:1.3}} .final-callout{{margin:45px auto;padding:32px;text-align:center;border:3px solid #0b7285;border-radius:15px;font-size:27px;line-height:1.35;max-width:650px}}
@media print{{.slide{{page-break-after:always;margin:0;box-shadow:none}}}}
</style></head><body><main class="deck">{''.join(slides)}</main></body></html>"""


def build_pdf(data: dict) -> None:
    pdf_path = OUT / "board_deck.pdf"
    page_width, page_height = landscape(A4)
    pdf = canvas.Canvas(str(pdf_path), pagesize=(page_width, page_height))
    pdf.setTitle("PulseIQ board handover")
    headcount = data["headcount"]
    attrition = data["attrition"]
    payroll = data["payroll"]
    teams = data["teams"]
    dso_value = float(data["dso"][0][1])
    checks = data["checks"]
    start_count, end_count = float(headcount[0][1]), float(headcount[-1][1])
    growth = 100 * (end_count - start_count) / start_count
    slides = [
        ("PulseIQ board handover", "Decision-ready monitoring with one cost-data hold.", "Approve monitoring; gate cost action on DQ-C01."),
        ("Finding 1 — workforce is scaling", f"Headcount: {start_count:,.0f} to {end_count:,.0f} (+{growth:.1f}%).", "Plan capacity and manager span."),
        ("Finding 2 — attrition needs the rolling lens", f"September monthly attrition: {float(attrition[-1][1]):.2f}%.", "Investigate persistent movement, not spikes."),
        ("Finding 3 — payroll is not decision-safe yet", f"September payroll: INR {float(payroll[-1][1]) / 1_000_000:.1f}M; June mismatch: INR 18,450.", "Close DQ-C01 before cost action."),
        ("Finding 4 — cash is tied up", f"DSO: {dso_value:.0f} days; top overdue account needs ownership.", "Run a weekly collections review."),
        ("Finding 5 — teams show a completion spread", f"Completion range: {float(teams[0][1]):.1f}% to {float(teams[-1][1]):.1f}%.", "Share planning and flow practices."),
        ("What is trusted now", "Warehouse and metric validation pass; live DQ is conditional.", "Use monitoring with the explicit caveat."),
        ("30 / 60 / 90-day decisions", "Close the issue, focus cash, improve planning.", "Return with a clean reconciliation."),
        ("Handover decision", "Use now for people, cash, and team monitoring; hold cost interventions.", "Accept handover and schedule DQ-C01 review."),
    ]
    for index, (title, finding, recommendation) in enumerate(slides, 1):
        pdf.setFillColor(colors.HexColor("#F4F7FB"))
        pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#0B7285"))
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(48, page_height - 45, f"{index:02d} / 09")
        pdf.setFillColor(colors.HexColor("#173D38"))
        pdf.setFont("Helvetica-Bold", 26)
        pdf.drawString(48, page_height - 92, title)
        pdf.setFont("Helvetica", 17)
        pdf.drawString(48, page_height - 130, finding)
        pdf.setFillColor(colors.HexColor("#EAF7F0"))
        pdf.roundRect(48, 120, page_width - 96, 75, 8, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#173D38"))
        pdf.setFont("Helvetica-Bold", 15)
        pdf.drawString(66, 168, "Recommendation")
        pdf.setFont("Helvetica", 15)
        pdf.drawString(66, 143, recommendation)
        pdf.setFont("Helvetica", 10)
        pdf.setFillColor(colors.HexColor("#71817F"))
        pdf.drawString(48, 75, "PulseIQ | Task 20 board handover | Data cut-off: 2026-09-30")
        pdf.showPage()
    pdf.save()


def main() -> None:
    data = load_board_data()
    (OUT / "board_deck.html").write_text(build_html(data), encoding="utf-8")
    build_pdf(data)
    (OUT / "board_data.json").write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"Built {OUT / 'board_deck.html'}")
    print(f"Built {OUT / 'board_deck.pdf'}")


if __name__ == "__main__":
    main()
