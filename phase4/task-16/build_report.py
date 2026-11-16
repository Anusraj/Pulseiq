"""Build a stamped monthly PulseIQ report pack.

Example:
    python build_report.py --month 2026-09 --output reports/pulseiq-2026-09.pdf
"""

from __future__ import annotations

import argparse
import calendar
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE = ROOT / "pulseiq.duckdb"
DEFAULT_OUTPUT = ROOT / "reports" / "pulseiq-monthly-report.pdf"
PAGE = landscape(A4)
INK = colors.HexColor("#1F2937")
BLUE = colors.HexColor("#2563EB")
PALE_BLUE = colors.HexColor("#EFF6FF")
GREEN = colors.HexColor("#15803D")
RED = colors.HexColor("#B91C1C")


def parse_month(value: str) -> tuple[date, date]:
    try:
        year, month = (int(part) for part in value.split("-"))
        start = date(year, month, 1)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError("month must use YYYY-MM format") from None
    return start, date(year, month, calendar.monthrange(year, month)[1])


def money(value: Any) -> str:
    return "—" if value is None else f"₹{float(value):,.0f}"


def number(value: Any, decimals: int = 1) -> str:
    return "—" if value is None else f"{float(value):,.{decimals}f}"


def percent(value: Any) -> str:
    return "—" if value is None else f"{float(value):,.2f}%"


def query_frame(connection: Any, sql: str, month: date, end: date):
    return connection.execute(sql, [month, end]).fetchdf()


def latest_cutoff(connection: Any, month: date, end: date) -> date:
    candidates: list[date] = []
    for view, column in (
        ("dashboard_executive_scorecard", "period_start"),
        ("dashboard_pnl_monthly", "period_start"),
        ("dashboard_payroll_department_month", "period_start"),
        ("dashboard_budget_vs_actual", "period_start"),
        ("dashboard_team_sprint_productivity", "sprint_end"),
    ):
        value = connection.execute(
            f"SELECT MAX({column}) FROM metrics.{view} WHERE {column} BETWEEN ? AND ?",
            [month, end],
        ).fetchone()[0]
        if value is not None:
            candidates.append(value)
    if not candidates:
        raise ValueError(f"No governed metric data exists for {month:%Y-%m}")
    return max(candidates)


def table(data: list[list[str]], widths: list[float], header: bool = True) -> Table:
    result = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    style = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_BLUE]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    result.setStyle(TableStyle(style))
    return result


class BarChart(Flowable):
    def __init__(self, labels: list[str], values: list[float], title: str, width=125 * mm, height=48 * mm):
        super().__init__()
        self.labels, self.values, self.title = labels, values, title
        self.width, self.height = width, height

    def draw(self) -> None:
        canvas = self.canv
        canvas.setFillColor(INK)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(0, self.height - 10, self.title)
        if not self.values or max(self.values) <= 0:
            canvas.setFont("Helvetica", 8)
            canvas.drawString(0, self.height / 2, "No chart data for this month")
            return
        chart_top = self.height - 17
        chart_height = self.height - 28
        bar_width = self.width / max(len(self.values), 1) * 0.65
        gap = self.width / max(len(self.values), 1)
        maximum = max(self.values)
        for index, value in enumerate(self.values):
            height = chart_height * value / maximum
            x = index * gap + (gap - bar_width) / 2
            canvas.setFillColor(BLUE)
            canvas.rect(x, 12, bar_width, height, fill=1, stroke=0)
            canvas.setFillColor(INK)
            canvas.setFont("Helvetica", 6)
            canvas.drawCentredString(x + bar_width / 2, 4, self.labels[index][:14])


def generate_report(database: Path, month: date, output: Path, generated_at: datetime | None = None) -> Path:
    end = date(month.year, month.month, calendar.monthrange(month.year, month.month)[1])
    output.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(database), read_only=True)
    try:
        cutoff = latest_cutoff(connection, month, end)
        scorecard = query_frame(
            connection,
            """SELECT kpi_name, metric_value, target_value, unit, traffic_light
               FROM metrics.dashboard_executive_scorecard
               WHERE period_start BETWEEN ? AND ? ORDER BY kpi_id""",
            month,
            end,
        )
        pnl = query_frame(
            connection,
            """SELECT revenue, operating_revenue, expenses, net_profit, operating_margin
               FROM metrics.dashboard_pnl_monthly WHERE period_start BETWEEN ? AND ?""",
            month,
            end,
        )
        payroll = query_frame(
            connection,
            """SELECT department_name, group_size, gross_pay, employer_cost, cost_per_employee
               FROM metrics.dashboard_payroll_department_month
               WHERE period_start BETWEEN ? AND ? ORDER BY employer_cost DESC""",
            month,
            end,
        )
        budget = query_frame(
            connection,
            """SELECT department_name, budget_payroll_cost, actual_payroll_cost,
                      variance, variance_pct, traffic_light
               FROM metrics.dashboard_budget_vs_actual
               WHERE period_start BETWEEN ? AND ? ORDER BY actual_payroll_cost DESC""",
            month,
            end,
        )
        productivity = query_frame(
            connection,
            """SELECT team_name, planned_tasks, completion_rate, on_time_rate,
                      velocity_points, average_cycle_days
               FROM metrics.dashboard_team_sprint_productivity
               WHERE period_start <= ? AND sprint_end >= ?
               ORDER BY team_name""",
            month,
            end,
        )
    finally:
        connection.close()

    styles = getSampleStyleSheet()
    title = ParagraphStyle("ReportTitle", parent=styles["Title"], fontSize=20, textColor=INK, alignment=TA_LEFT)
    heading = ParagraphStyle("Heading", parent=styles["Heading2"], fontSize=13, textColor=INK, spaceBefore=4, spaceAfter=7)
    small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#475569"))
    story: list[Any] = [
        Paragraph("PulseIQ monthly management report", title),
        Paragraph(
            f"<b>Reporting period:</b> {month:%d %B %Y} – {end:%d %B %Y} &nbsp;&nbsp; "
            f"<b>Data cut-off:</b> {cutoff:%d %B %Y} &nbsp;&nbsp; "
            f"<b>Generated:</b> {(generated_at or datetime.now()).astimezone():%d %B %Y %H:%M %Z}",
            small,
        ),
        Spacer(1, 8),
        Paragraph("This pack contains five governed views. Department and team rows are discovered from the warehouse at run time.", small),
        Spacer(1, 10),
    ]

    story.append(Paragraph("1. Executive KPI scorecard", heading))
    score_rows = [["KPI", "Value", "Target", "Status"]]
    for row in scorecard.itertuples(index=False):
        formatter = money if row.unit == "INR" else percent if row.unit == "%" else number
        score_rows.append([row.kpi_name, formatter(row.metric_value), formatter(row.target_value) if row.target_value == row.target_value else "Not set", row.traffic_light])
    story.append(table(score_rows, [75 * mm, 35 * mm, 35 * mm, 35 * mm]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("2. P&L summary", heading))
    pnl_rows = [["Revenue", "Operating revenue", "Expenses", "Net profit", "Operating margin"]]
    if not pnl.empty:
        row = pnl.iloc[0]
        pnl_rows.append([money(row.revenue), money(row.operating_revenue), money(row.expenses), money(row.net_profit), percent(row.operating_margin)])
    else:
        pnl_rows.append(["—"] * 5)
    story.append(table(pnl_rows, [42 * mm] * 5))
    story.append(Spacer(1, 8))

    story.append(Paragraph("3. Payroll by department", heading))
    payroll_rows = [["Department", "People", "Gross pay", "Employer cost", "Cost / person"]]
    for row in payroll.itertuples(index=False):
        payroll_rows.append([row.department_name, number(row.group_size, 0), money(row.gross_pay), money(row.employer_cost), money(row.cost_per_employee)])
    story.append(table(payroll_rows, [65 * mm, 25 * mm, 38 * mm, 42 * mm, 38 * mm]))
    story.append(PageBreak())

    story.append(Paragraph("4. Budget versus actual payroll", heading))
    budget_rows = [["Department", "Budget", "Actual", "Variance", "Variance %", "Status"]]
    for row in budget.itertuples(index=False):
        budget_rows.append([row.department_name, money(row.budget_payroll_cost), money(row.actual_payroll_cost), money(row.variance), percent(row.variance_pct), row.traffic_light])
    story.append(table(budget_rows, [55 * mm, 35 * mm, 35 * mm, 35 * mm, 30 * mm, 25 * mm]))
    story.append(Spacer(1, 8))
    story.append(BarChart(
        budget["department_name"].astype(str).tolist(),
        budget["actual_payroll_cost"].fillna(0).astype(float).tolist(),
        "Actual payroll cost by department",
    ))

    story.append(Paragraph("5. Team productivity", heading))
    product_rows = [["Team", "Planned tasks", "Completion", "On time", "Velocity", "Cycle days"]]
    for row in productivity.itertuples(index=False):
        product_rows.append([row.team_name, number(row.planned_tasks, 0), percent(row.completion_rate), percent(row.on_time_rate), number(row.velocity_points), number(row.average_cycle_days)])
    story.append(table(product_rows, [55 * mm, 28 * mm, 30 * mm, 30 * mm, 28 * mm, 28 * mm]))
    story.append(Spacer(1, 8))
    story.append(BarChart(
        productivity["team_name"].astype(str).tolist(),
        productivity["completion_rate"].fillna(0).astype(float).tolist(),
        "Completion rate by team (%)",
    ))

    class NumberedDocTemplate(BaseDocTemplate):
        def afterPage(self):
            self.canv.saveState()
            self.canv.setFont("Helvetica", 7)
            self.canv.setFillColor(colors.HexColor("#64748B"))
            self.canv.drawRightString(PAGE[0] - 15 * mm, 8 * mm, f"PulseIQ | {month:%Y-%m} | Page {self.page}")
            self.canv.restoreState()

    document = NumberedDocTemplate(
        str(output), pagesize=PAGE,
        leftMargin=15 * mm, rightMargin=15 * mm, topMargin=12 * mm, bottomMargin=14 * mm,
    )
    frame = Frame(document.leftMargin, document.bottomMargin, document.width, document.height, id="normal")
    document.addPageTemplates([PageTemplate(id="report", frames=frame)])
    document.build(story)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a stamped PulseIQ monthly PDF report.")
    parser.add_argument("--month", required=True, type=parse_month, help="Reporting month in YYYY-MM format")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    month, _ = args.month
    output = args.output or ROOT / "reports" / f"pulseiq-{month:%Y-%m}.pdf"
    try:
        path = generate_report(args.database, month, output)
    except (duckdb.Error, OSError, ValueError) as exc:
        raise SystemExit(f"Report build failed: {exc}") from exc
    print(f"Created {path}")


if __name__ == "__main__":
    main()
