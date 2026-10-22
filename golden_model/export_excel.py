"""Write the verification results to a professional Excel workbook.

    verification_results.xlsx
      Summary  - run info, pass/fail totals, latency statistics (live formulas) + latency chart
      Results  - one row per input vector: inputs, golden vs RTL outputs, bit streams,
                 latency in cycles and ns, PASS/FAIL (every check is an Excel formula)
      History  - one row appended per run (date/time, input, totals, latency) so runs can be compared

Needs the third-party package openpyxl:   pip install openpyxl
It is optional: run_verification.py prints a hint and carries on when it is missing.
"""

from datetime import datetime
from pathlib import Path

CLOCK_PERIOD_NS = 10            # tb_tdm_top_filebased.v: always #5 clk = ~clk  -> 10 ns

FONT = "Arial"


def _styles():
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    thin = Side(style="thin", color="B8C2CC")
    return {
        "title": Font(name=FONT, size=15, bold=True, color="1F3A5F"),
        "section": Font(name=FONT, size=11, bold=True, color="FFFFFF"),
        "section_fill": PatternFill("solid", fgColor="2E5E8C"),
        "head": Font(name=FONT, size=10, bold=True, color="FFFFFF"),
        "head_fill": PatternFill("solid", fgColor="1F3A5F"),
        "body": Font(name=FONT, size=10),
        "bold": Font(name=FONT, size=10, bold=True),
        "mono": Font(name="Consolas", size=10),
        "input": Font(name=FONT, size=10, color="0000FF"),
        "input_fill": PatternFill("solid", fgColor="FFFF99"),
        "note": Font(name=FONT, size=9, italic=True, color="666666"),
        "border": Border(left=thin, right=thin, top=thin, bottom=thin),
        "center": Alignment(horizontal="center", vertical="center"),
        "left": Alignment(horizontal="left", vertical="center"),
        "wrap": Alignment(horizontal="center", vertical="center", wrap_text=True),
    }


def _add_status_formatting(ws, cell_range):
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.styles import Font, PatternFill

    good = dict(font=Font(name=FONT, size=10, bold=True, color="006100"),
                fill=PatternFill("solid", bgColor="C6EFCE", fgColor="C6EFCE"))
    bad = dict(font=Font(name=FONT, size=10, bold=True, color="9C0006"),
               fill=PatternFill("solid", bgColor="FFC7CE", fgColor="FFC7CE"))
    for word in ('"PASS"', '"MATCH"', '"OK"'):
        ws.conditional_formatting.add(cell_range, CellIsRule(operator="equal", formula=[word], **good))
    for word in ('"FAIL"', '"MISMATCH"', '"OVER LIMIT"', '"NEVER"'):
        ws.conditional_formatting.add(cell_range, CellIsRule(operator="equal", formula=[word], **bad))


def _build_results(ws, st, results):
    heads = [
        ("#", 6), ("Type", 12), ("Input (hex)", 13),
        ("CH0 in", 8), ("CH1 in", 8), ("CH2 in", 8), ("CH3 in", 8),
        ("Golden CHx_OUT (hex)", 16), ("RTL CHx_OUT (hex)", 16), ("Output check", 12),
        ("Golden bit stream (32 bit)", 36), ("RTL bit stream (32 bit)", 36), ("Stream check", 12),
        ("Latency (cycles)", 11), ("Latency (ns)", 11), ("Latency check", 13), ("Result", 10),
    ]
    for c, (h, w) in enumerate(heads, start=1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font, cell.fill, cell.alignment, cell.border = st["head"], st["head_fill"], st["wrap"], st["border"]
        ws.column_dimensions[cell.column_letter].width = w
    ws.row_dimensions[1].height = 32

    n = len(results)
    for i, r in enumerate(results):
        row = i + 2
        vals = {
            "A": r["index"],
            "B": "Cold start" if r["index"] == 0 else "Mid-stream",
            "C": r["input"].upper(),
            "D": f"=MID(C{row},1,2)", "E": f"=MID(C{row},3,2)",
            "F": f"=MID(C{row},5,2)", "G": f"=MID(C{row},7,2)",
            "H": r["golden_out"].upper(),
            "I": r["rtl_out"].upper(),
            "J": f'=IF(H{row}=I{row},"MATCH","MISMATCH")',
            "K": r["golden_stream"],
            "L": r["rtl_stream"],
            "M": f'=IF(K{row}=L{row},"MATCH","MISMATCH")',
            "N": r["latency"],
            "O": f'=IF(N{row}<0,"n/a",N{row}*Summary!$B$9)',
            "P": f'=IF(N{row}<0,"NEVER",IF(N{row}<=Summary!$B$10,"OK","OVER LIMIT"))',
            "Q": f'=IF(AND(J{row}="MATCH",M{row}="MATCH",P{row}="OK"),"PASS","FAIL")',
        }
        for col, v in vals.items():
            cell = ws[f"{col}{row}"]
            cell.value = v
            cell.border = st["border"]
            cell.font = st["mono"] if col in "CDEFGHIKL" else st["body"]
            cell.alignment = st["left"] if col in "KL" else st["center"]
        ws[f"O{row}"].number_format = "0"
    last = n + 1
    ws.freeze_panes = "D2"
    ws.auto_filter.ref = f"A1:Q{last}"
    _add_status_formatting(ws, f"J2:J{last}")
    _add_status_formatting(ws, f"M2:M{last}")
    _add_status_formatting(ws, f"P2:Q{last}")
    return last


def _build_summary(ws, st, summary, meta, last):
    from openpyxl.chart import BarChart, Reference
    from openpyxl.comments import Comment

    lat = summary["latency"]
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 62
    ws.column_dimensions["C"].width = 16

    ws["A1"] = "TDM 4-Channel Mux/Demux - RTL vs Golden Model Verification"
    ws["A1"].font = st["title"]

    def section(row, text):
        for col in "ABC":
            ws[f"{col}{row}"].fill = st["section_fill"]
        ws[f"A{row}"] = text
        ws[f"A{row}"].font = st["section"]

    def line(row, label, value, fmt=None, bold=False, mono=False):
        ws[f"A{row}"] = label
        ws[f"A{row}"].font = st["bold"]
        ws[f"B{row}"] = value
        ws[f"B{row}"].font = st["bold"] if bold else (st["mono"] if mono else st["body"])
        ws[f"B{row}"].alignment = st["left"]
        for col in "AB":
            ws[f"{col}{row}"].border = st["border"]
        if fmt:
            ws[f"B{row}"].number_format = fmt

    section(3, "Run information")
    line(4, "Run date / time", meta["timestamp"])
    line(5, "Input file", summary["input_file"])
    line(6, "Simulator / tool", meta.get("simulator", ""))
    line(7, "Reference model", "Python golden model (golden_model.TDMGoldenModel)")
    line(8, "Design under test", "tdm_top (tdm_counter, tdm_mux, tx_shift_reg, rx_shift_reg, tdm_demux)")

    line(9, "Clock period (ns)", CLOCK_PERIOD_NS)
    line(10, "Max allowed latency (cycles)", lat["max_allowed"])
    for r in (9, 10):
        ws[f"B{r}"].font, ws[f"B{r}"].fill = st["input"], st["input_fill"]
    ws["B9"].comment = Comment("Assumption: tb_tdm_top_filebased.v generates the clock with "
                               "'always #5 clk = ~clk' and timescale 1ns/1ps, i.e. 10 ns. "
                               "Edit this cell if the testbench clock changes.", "golden_model")
    ws["B10"].comment = Comment("Source: golden_model/latency_checker.py MAX_LATENCY = 41 "
                                "(31 wait for load slot + 8 serialise + 2 output registers; "
                                "verified by sweeping all 32 bit_count phases).", "golden_model")
    ws["C9"] = "<- editable"
    ws["C10"] = "<- editable"
    ws["C9"].font = ws["C10"].font = st["note"]

    rng = lambda col: f"Results!${col}$2:${col}${last}"
    section(12, "Verification summary")
    line(13, "Total vectors", f"=COUNTA({rng('A')})", "0")
    line(14, "Vectors passed", f'=COUNTIF({rng("Q")},"PASS")', "0")
    line(15, "Vectors failed", "=B13-B14", "0")
    line(16, "Pass rate", "=IF(B13=0,0,B14/B13)", "0.0%")
    line(17, "Overall status", '=IF(AND(B13>0,B15=0,B26="PASS"),"PASS","FAIL")', bold=True)

    section(19, "Latency")
    ws["B19"], ws["C19"] = "Cycles", "ns"
    for c in ("B19", "C19"):
        ws[c].font = st["section"]
        ws[c].alignment = st["center"]
    ws["A20"] = "Cold start (vector 0)"
    ws["B20"] = "=Results!N2"
    has_mid = last >= 3
    ws["A21"] = "Mid-stream minimum"
    ws["B21"] = f"=MIN(Results!$N$3:$N${last})" if has_mid else "n/a"
    ws["A22"] = "Mid-stream maximum"
    ws["B22"] = f"=MAX(Results!$N$3:$N${last})" if has_mid else "n/a"
    ws["A23"] = "Mid-stream average"
    ws["B23"] = f"=AVERAGE(Results!$N$3:$N${last})" if has_mid else "n/a"
    ws["A24"] = "Worst case of all vectors"
    ws["B24"] = f"=MAX({rng('N')})"
    ws["A25"] = "Allowed maximum"
    ws["B25"] = "=B10"
    ws["A26"] = "Latency check"
    ws["B26"] = f'=IF(AND(MIN({rng("N")})>=0,MAX({rng("N")})<=B10),"PASS","FAIL")'
    for r in range(20, 27):
        ws[f"A{r}"].font = st["bold"]
        ws[f"B{r}"].font = st["bold"] if r == 26 else st["body"]
        ws[f"B{r}"].alignment = st["center"]
        ws[f"A{r}"].border = ws[f"B{r}"].border = st["border"]
        if r < 26:
            ws[f"B{r}"].number_format = "0.0" if r == 23 else "0"
            ws[f"C{r}"] = f'=IF(ISNUMBER(B{r}),B{r}*$B$9,"n/a")'
            ws[f"C{r}"].font, ws[f"C{r}"].alignment, ws[f"C{r}"].border = st["body"], st["center"], st["border"]
            ws[f"C{r}"].number_format = "0.0"
    _add_status_formatting(ws, "B17")
    _add_status_formatting(ws, "B26")

    ws["A28"] = ("Notes: vector 0 is a cold start (latency counted from reset release); later vectors change "
                 "the inputs mid-stream at bit_count = 24. All check columns on the Results sheet are formulas; "
                 "if values look empty, click 'Enable Editing' in Excel.")
    ws["A28"].font = st["note"]

    ch = BarChart()
    ch.type = "col"
    ch.title = "Latency per input vector"
    ch.y_axis.title = "Latency (clock cycles)"
    ch.x_axis.title = "Vector #"
    ch.add_data(Reference(wr := summary["_results_ws"], min_col=14, min_row=1, max_row=last), titles_from_data=True)
    ch.set_categories(Reference(wr, min_col=1, min_row=2, max_row=last))
    ch.legend = None
    ch.height, ch.width = 8.5, 17
    ch.y_axis.delete = False
    ch.x_axis.delete = False
    ws.add_chart(ch, "E3")


def _append_history(wb, st, summary, meta, xlsx_name):
    heads = ["Run date / time", "Input file", "Simulator / tool", "Vectors", "Passed", "Failed",
             "Cold start latency (cycles)", "Max latency (cycles)", "Overall", "Results file"]
    if "History" in wb.sheetnames:
        ws = wb["History"]
    else:
        ws = wb.create_sheet("History")
        for c, h in enumerate(heads, start=1):
            cell = ws.cell(row=1, column=c, value=h)
            cell.font, cell.fill, cell.alignment, cell.border = st["head"], st["head_fill"], st["wrap"], st["border"]
        for col, w in zip("ABCDEFGHIJ", (20, 24, 28, 9, 9, 9, 16, 14, 10, 30)):
            ws.column_dimensions[col].width = w
        ws.row_dimensions[1].height = 32
        ws.freeze_panes = "A2"

    results = summary["results"]
    lat = summary["latency"]
    passed = sum(1 for r in results if r["ok"])
    row = ws.max_row + 1
    values = [meta["timestamp"], summary["input_file"], meta.get("simulator", ""), len(results), passed,
              len(results) - passed, lat["cold_start"],
              max((r["latency"] for r in results), default=None),
              "PASS" if summary["all_pass"] else "FAIL", xlsx_name]
    for c, v in enumerate(values, start=1):
        cell = ws.cell(row=row, column=c, value=v)
        cell.font, cell.border = st["body"], st["border"]
        cell.alignment = st["left"] if c in (1, 2, 3, 10) else st["center"]
    ws.auto_filter.ref = f"A1:J{row}"
    _add_status_formatting(ws, f"I2:I{max(row, 2)}")


def write_excel(path, summary, simulator=""):
    """Create / refresh the workbook. summary = same dict as report_generator.write_report
    (input_file, results, latency, all_pass). Returns the path written."""

    from openpyxl import Workbook, load_workbook

    path = Path(path)
    st = _styles()
    meta = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "simulator": simulator}

    if path.exists():
        wb = load_workbook(path)
        for name in ("Summary", "Results"):          # rebuilt on every run; History is kept
            if name in wb.sheetnames:
                del wb[name]
    else:
        wb = Workbook()
        wb.remove(wb.active)

    ws_sum = wb.create_sheet("Summary", 0)
    ws_res = wb.create_sheet("Results", 1)
    last = _build_results(ws_res, st, summary["results"])
    summary = dict(summary, _results_ws=ws_res)
    _build_summary(ws_sum, st, summary, meta, last)
    _append_history(wb, st, summary, meta, path.name)

    from openpyxl.worksheet.properties import PageSetupProperties
    for ws in (ws_sum, ws_res, wb["History"]):          # print: landscape, one page wide
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws_res.print_title_rows = "1:1"

    ws_sum.sheet_properties.tabColor = "1F3A5F"
    ws_res.sheet_properties.tabColor = "2E5E8C"
    wb.active = 0
    wb.save(path)
    return path
