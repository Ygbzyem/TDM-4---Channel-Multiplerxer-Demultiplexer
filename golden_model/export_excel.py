"""Write the verification results to a professional Excel workbook.

    verification_results.xlsx   (every run is APPENDED, nothing is overwritten)
      Summary  - latest run (totals, latency in cycles and ns, chart) and the cumulative totals of
                 all runs; live formulas
      Results  - one row per input vector of EVERY run (Run #, date/time, input file, size
                 NUM_CHANNELS x DATA_WIDTH, inputs, golden vs RTL outputs and bit streams, latency
                 and its allowed maximum, PASS/FAIL); every check is an Excel formula; filter by
                 "Run #" to look at a single run
      History  - one row per run (date/time, input, totals, latency)

Needs the third-party package openpyxl:   python -m pip install openpyxl
It is optional: run_verification.py prints a hint and carries on when it is missing.
"""

from datetime import datetime
from pathlib import Path

CLOCK_PERIOD_NS = 10            # tb_tdm_top_filebased.v: always #5 clk = ~clk  -> 10 ns
FONT = "Arial"

# fixed cell on the Summary sheet that the Results formulas refer to
CLOCK_CELL = "Summary!$B$11"

# Results columns: A Run #, B date, C input file, D size, E vector #, F type, G input,
# H channel words, I golden outputs, J RTL outputs, K output check, L golden stream,
# M RTL stream, N stream check, O latency, P latency ns, Q allowed max, R latency check, S result
RESULT_HEADS = [
    ("Run #", 7), ("Run date / time", 18), ("Input file", 22), ("Size (N x W)", 10), ("Vector #", 9),
    ("Type", 12), ("Input (hex, CH0 first)", 20), ("Channel words in (CH0 CH1 ...)", 26),
    ("Golden outputs (hex)", 20), ("RTL outputs (hex)", 20), ("Output check", 12),
    ("Golden bit stream (one frame)", 36), ("RTL bit stream (one frame)", 36), ("Stream check", 12),
    ("Latency (cycles)", 11), ("Latency (ns)", 11), ("Allowed max (cycles)", 11),
    ("Latency check", 13), ("Result", 10),
]
LAST_COL = "S"
HISTORY_HEADS = [
    ("Run #", 7), ("Run date / time", 20), ("Input file", 24), ("Size (N x W)", 10),
    ("Simulator / tool", 28), ("Vectors", 9), ("Passed", 9), ("Failed", 9),
    ("Cold start latency (cycles)", 16), ("Max latency (cycles)", 14), ("Overall", 10),
]


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
        "band": PatternFill("solid", fgColor="EEF3F8"),
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


def _write_header(ws, st, heads):
    for c, (h, w) in enumerate(heads, start=1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font, cell.fill, cell.alignment, cell.border = st["head"], st["head_fill"], st["wrap"], st["border"]
        ws.column_dimensions[cell.column_letter].width = w
    ws.row_dimensions[1].height = 32


def _append_results(ws, st, results, run_no, stamp, input_file, size, maxlat):
    """Append one block of rows (this run) below the existing ones. Returns (first_row, last_row)."""
    first = ws.max_row + 1
    for i, r in enumerate(results):
        row = first + i
        vals = {
            "A": run_no, "B": stamp, "C": input_file, "D": size,
            "E": r["index"],
            "F": "Cold start" if r["index"] == 0 else "Mid-stream",
            "G": r["input"].upper(),
            "H": r.get("channels_in", "").upper(),
            "I": r["golden_out"].upper(),
            "J": r["rtl_out"].upper(),
            "K": f'=IF(I{row}=J{row},"MATCH","MISMATCH")',
            "L": r["golden_stream"],
            "M": r["rtl_stream"],
            "N": f'=IF(L{row}=M{row},"MATCH","MISMATCH")',
            "O": r["latency"],
            "P": f'=IF(O{row}<0,"n/a",O{row}*{CLOCK_CELL})',
            "Q": maxlat,
            "R": f'=IF(O{row}<0,"NEVER",IF(O{row}<=Q{row},"OK","OVER LIMIT"))',
            "S": f'=IF(AND(K{row}="MATCH",N{row}="MATCH",R{row}="OK"),"PASS","FAIL")',
        }
        for col, v in vals.items():
            cell = ws[f"{col}{row}"]
            cell.value = v
            cell.border = st["border"]
            cell.font = st["mono"] if col in "GHIJLM" else st["body"]
            cell.alignment = st["left"] if col in "BCHLM" else st["center"]
            if run_no % 2 == 0:                       # light band so runs are easy to tell apart
                cell.fill = st["band"]
        ws[f"P{row}"].number_format = "0"
    return first, ws.max_row


def _build_summary(ws, st, summary, meta, run_no, first, last, clock, maxlat):
    size = summary.get("size", "4 x 8")
    from openpyxl.chart import BarChart, Reference
    from openpyxl.comments import Comment

    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 62
    ws.column_dimensions["C"].width = 16
    ws["A1"] = "TDM Mux/Demux - RTL vs Golden Model Verification"
    ws["A1"].font = st["title"]

    def section(row, text):
        for col in "ABC":
            ws[f"{col}{row}"].fill = st["section_fill"]
        ws[f"A{row}"] = text
        ws[f"A{row}"].font = st["section"]

    def line(row, label, value, fmt=None, bold=False):
        ws[f"A{row}"] = label
        ws[f"A{row}"].font = st["bold"]
        ws[f"B{row}"] = value
        ws[f"B{row}"].font = st["bold"] if bold else st["body"]
        ws[f"B{row}"].alignment = st["left"]
        for col in "AB":
            ws[f"{col}{row}"].border = st["border"]
        if fmt:
            ws[f"B{row}"].number_format = fmt

    allr = lambda col: f"Results!${col}$2:${col}${last}"          # every run
    cur = lambda col: f"Results!${col}${first}:${col}${last}"     # latest run only

    section(3, "Run information (latest run)")
    line(4, "Latest run #", run_no, "0")
    line(5, "Run date / time", meta["timestamp"])
    line(6, "Input file", summary["input_file"])
    line(7, "Simulator / tool", meta.get("simulator", ""))
    line(8, "Reference model", "Python golden model (golden_model.TDMGoldenModel)")
    line(9, "Design under test", f"tdm_top, NUM_CHANNELS x DATA_WIDTH = {size} "
                                 "(tdm_counter, tdm_mux, tx_shift_reg, rx_shift_reg, tdm_demux)")
    line(10, "Runs recorded in this workbook", f"=MAX({allr('A')})", "0")
    line(11, "Clock period (ns)", clock)
    line(12, "Max allowed latency (cycles)", maxlat)
    ws["B11"].font, ws["B11"].fill = st["input"], st["input_fill"]
    ws["C11"] = "<- editable"
    ws["C11"].font = st["note"]
    ws["B11"].comment = Comment("Assumption: tb_tdm_top_filebased.v generates the clock with "
                                "'always #5 clk = ~clk' and timescale 1ns/1ps, i.e. 10 ns. "
                                "Edit this cell if the testbench clock changes.", "golden_model")
    ws["B12"].comment = Comment("Source: golden_model/latency_checker.py max_latency(N, W) = N*W + W + 1 "
                                "(N*W-1 wait for the load slot + W serialise + 2 output registers); "
                                "41 for 4 x 8. Each Results row keeps the maximum of its own size.",
                                "golden_model")

    section(14, "Latest run - verification summary")
    line(15, "Total vectors", f"=COUNTA({cur('E')})", "0")
    line(16, "Vectors passed", f'=COUNTIF({cur("S")},"PASS")', "0")
    line(17, "Vectors failed", "=B15-B16", "0")
    line(18, "Pass rate", "=IF(B15=0,0,B16/B15)", "0.0%")
    line(19, "Overall status", '=IF(AND(B15>0,B17=0,B28="PASS"),"PASS","FAIL")', bold=True)

    section(21, "Latest run - latency")
    ws["B21"], ws["C21"] = "Cycles", "ns"
    for c in ("B21", "C21"):
        ws[c].font, ws[c].alignment = st["section"], st["center"]
    has_mid = last - first >= 1
    first_mid = first + 1
    rows = [
        (22, "Cold start (vector 0)", f"=Results!O{first}"),
        (23, "Mid-stream minimum", f"=MIN(Results!$O${first_mid}:$O${last})" if has_mid else "n/a"),
        (24, "Mid-stream maximum", f"=MAX(Results!$O${first_mid}:$O${last})" if has_mid else "n/a"),
        (25, "Mid-stream average", f"=AVERAGE(Results!$O${first_mid}:$O${last})" if has_mid else "n/a"),
        (26, "Worst case of all vectors", f"=MAX({cur('O')})"),
        (27, "Allowed maximum", "=B12"),
        (28, "Latency check", f'=IF(COUNTIF({cur("R")},"OK")=COUNTA({cur("E")}),"PASS","FAIL")'),
    ]
    for r, label, f in rows:
        ws[f"A{r}"], ws[f"B{r}"] = label, f
        ws[f"A{r}"].font = st["bold"]
        ws[f"B{r}"].font = st["bold"] if r == 28 else st["body"]
        ws[f"B{r}"].alignment = st["center"]
        ws[f"A{r}"].border = ws[f"B{r}"].border = st["border"]
        if r < 28:
            ws[f"B{r}"].number_format = "0.0" if r == 25 else "0"
            ws[f"C{r}"] = f'=IF(ISNUMBER(B{r}),B{r}*$B$11,"n/a")'
            ws[f"C{r}"].font, ws[f"C{r}"].alignment, ws[f"C{r}"].border = st["body"], st["center"], st["border"]
            ws[f"C{r}"].number_format = "0.0"

    section(30, "All runs (cumulative)")
    line(31, "Runs recorded", "=B10", "0")
    line(32, "Total vectors checked", f"=COUNTA({allr('E')})", "0")
    line(33, "Vectors passed", f'=COUNTIF({allr("S")},"PASS")', "0")
    line(34, "Vectors failed", "=B32-B33", "0")
    line(35, "Pass rate", "=IF(B32=0,0,B33/B32)", "0.0%")
    line(36, "Worst latency of all runs (cycles)", f"=MAX({allr('O')})", "0")
    line(37, "Average mid-stream latency (cycles)",
         f'=IFERROR(AVERAGEIF({allr("F")},"Mid-stream",{allr("O")}),"n/a")', "0.0")
    line(38, "Overall status (all runs)",
         f'=IF(AND(B32>0,B34=0,COUNTIF({allr("R")},"OK")=B32),"PASS","FAIL")', bold=True)
    for r in (19, 28, 38):
        ws[f"B{r}"].alignment = st["center"] if r == 28 else st["left"]
    _add_status_formatting(ws, "B19")
    _add_status_formatting(ws, "B28")
    _add_status_formatting(ws, "B38")

    ws["A40"] = ("Every run is appended to the Results sheet (filter by Run #); the sections above are formulas "
                 "over the Results sheet. Vector 0 of a run is a cold start (latency counted from reset release); "
                 "later vectors change the inputs mid-stream at bit_count = (N-1) x W (24 for 4 x 8). Runs of "
                 "different sizes can share the workbook (column Size). If values look empty, click "
                 "'Enable Editing' in Excel.")
    ws["A40"].font = st["note"]

    ch = BarChart()
    ch.type = "col"
    ch.title = f"Latency per input vector - run #{run_no}"
    ch.y_axis.title = "Latency (clock cycles)"
    ch.x_axis.title = "Vector #"
    res_ws = summary["_results_ws"]
    ch.add_data(Reference(res_ws, min_col=15, min_row=first, max_row=last), titles_from_data=False)
    ch.set_categories(Reference(res_ws, min_col=5, min_row=first, max_row=last))
    ch.legend = None
    ch.height, ch.width = 8.5, 17
    ch.y_axis.delete = False
    ch.x_axis.delete = False
    ws.add_chart(ch, "E3")


def _append_history(ws, st, summary, meta, run_no):
    from openpyxl.formatting.formatting import ConditionalFormattingList
    results, lat = summary["results"], summary["latency"]
    passed = sum(1 for r in results if r["ok"])
    row = ws.max_row + 1
    values = [run_no, meta["timestamp"], summary["input_file"], summary.get("size", "4 x 8"),
              meta.get("simulator", ""),
              len(results), passed, len(results) - passed, lat["cold_start"],
              max((r["latency"] for r in results), default=None),
              "PASS" if summary["all_pass"] else "FAIL"]
    for c, v in enumerate(values, start=1):
        cell = ws.cell(row=row, column=c, value=v)
        cell.font, cell.border = st["body"], st["border"]
        cell.alignment = st["left"] if c in (2, 3, 5) else st["center"]
    ws.auto_filter.ref = f"A1:K{row}"
    ws.conditional_formatting = ConditionalFormattingList()
    _add_status_formatting(ws, f"K2:K{max(row, 2)}")


def write_excel(path, summary, simulator=""):
    """Append this run to the workbook (created on first use). summary = same dict as
    report_generator.write_report (input_file, results, latency, all_pass). Returns the path."""

    from openpyxl import Workbook, load_workbook
    from openpyxl.formatting.formatting import ConditionalFormattingList
    from openpyxl.worksheet.properties import PageSetupProperties

    path = Path(path)
    st = _styles()
    meta = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "simulator": simulator}
    clock, maxlat = CLOCK_PERIOD_NS, summary["latency"]["max_allowed"]

    if path.exists():
        wb = load_workbook(path)
        if "Summary" in wb.sheetnames:                  # keep the user's edit of the yellow cell
            old = wb["Summary"]
            if isinstance(old["B11"].value, (int, float)):
                clock = old["B11"].value
            del wb["Summary"]
        for name, heads in (("Results", RESULT_HEADS), ("History", HISTORY_HEADS)):
            if name in wb.sheetnames:
                ws_old = wb[name]
                current = [ws_old.cell(row=1, column=c).value for c in range(1, len(heads) + 1)]
                if current != [h for h, _ in heads]:      # sheet from an older layout: keep it, renamed
                    k, title = 1, f"{name} (old layout)"
                    while title in wb.sheetnames:
                        k += 1
                        title = f"{name} (old layout {k})"
                    ws_old.title = title[:31]
    else:
        wb = Workbook()
        wb.remove(wb.active)

    ws_sum = wb.create_sheet("Summary", 0)
    if "Results" in wb.sheetnames:
        ws_res = wb["Results"]
    else:
        ws_res = wb.create_sheet("Results", 1)
        _write_header(ws_res, st, RESULT_HEADS)
        ws_res.freeze_panes = "G2"
    if "History" in wb.sheetnames:
        ws_his = wb["History"]
    else:
        ws_his = wb.create_sheet("History")
        _write_header(ws_his, st, HISTORY_HEADS)
        ws_his.freeze_panes = "A2"

    previous = [c.value for c in ws_res["A"][1:] if isinstance(c.value, (int, float))]
    run_no = int(max(previous)) + 1 if previous else 1

    first, last = _append_results(ws_res, st, summary["results"], run_no, meta["timestamp"],
                                  summary["input_file"], summary.get("size", "4 x 8"), maxlat)
    ws_res.auto_filter.ref = f"A1:{LAST_COL}{last}"
    ws_res.conditional_formatting = ConditionalFormattingList()      # no duplicate rules after many runs
    for rng in (f"K2:K{last}", f"N2:N{last}", f"R2:S{last}"):
        _add_status_formatting(ws_res, rng)

    summary = dict(summary, _results_ws=ws_res)
    _build_summary(ws_sum, st, summary, meta, run_no, first, last, clock, maxlat)
    _append_history(ws_his, st, summary, meta, run_no)

    for ws in (ws_sum, ws_res, ws_his):                     # print: landscape, one page wide
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
