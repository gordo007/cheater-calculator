#!/usr/bin/env python3
"""Profile and clean a messy CSV (or .xlsx, if openpyxl is installed).

Usage:
    python3 tools/clean_data.py INPUT [-o OUTPUT.csv] [-r REPORT.md] [--dayfirst]

What it does, in order:
  1. Normalizes headers to snake_case and makes them unique.
  2. Trims whitespace and maps missing-value tokens (N/A, null, -, ...) to empty.
  3. Drops fully empty rows and columns, then exact duplicate rows.
  4. Infers numeric and date columns (>= 80% of non-empty values must parse)
     and normalizes them: numbers lose currency symbols / thousands separators,
     dates become ISO 8601 (YYYY-MM-DD). Values that don't parse are kept
     as-is and listed in the report so a human can check them.
  5. Writes the cleaned CSV and a Markdown report of every change.

Standard library only, so it runs anywhere Python 3.9+ is installed.
"""

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

MISSING_TOKENS = {"", "na", "n/a", "nan", "null", "none", "nil", "-", "--", "?", "#n/a"}
INFER_THRESHOLD = 0.8
DATE_FORMATS_YEAR_FIRST = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]
DATE_FORMATS_NAMED = ["%b %d %Y", "%b %d, %Y", "%B %d %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y", "%d-%b-%Y"]
DATE_FORMATS_MONTHFIRST = ["%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y"]
DATE_FORMATS_DAYFIRST = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y"]
NUMBER_RE = re.compile(r"^[+-]?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?$")


def snake_case(name):
    name = re.sub(r"[^0-9a-zA-Z]+", "_", name.strip()).strip("_").lower()
    return name or "column"


def unique_headers(headers):
    seen, out = {}, []
    for h in headers:
        base = snake_case(h)
        n = seen.get(base, 0)
        seen[base] = n + 1
        out.append(base if n == 0 else f"{base}_{n + 1}")
    return out


def parse_number(value):
    """Return a float for '$1,234.50', '(42)', '€ 7' etc., or None."""
    v = value.strip()
    negative = v.startswith("(") and v.endswith(")")
    if negative:
        v = v[1:-1]
    v = re.sub(r"[$€£¥\s]", "", v)
    if v.upper().endswith(("USD", "EUR", "GBP")):
        v = v[:-3]
    if not NUMBER_RE.match(v):
        return None
    num = float(v.replace(",", ""))
    return -num if negative else num


def format_number(num):
    return str(int(num)) if num.is_integer() else repr(num)


def parse_date(value, formats):
    v = value.strip()
    for fmt in formats:
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return None


def pick_date_formats(values, dayfirst):
    """Decide day-first vs month-first for slash dates; return (formats, ambiguous)."""
    first_parts, second_parts = [], []
    for v in values:
        m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-]\d{2,4}$", v.strip())
        if m:
            first_parts.append(int(m.group(1)))
            second_parts.append(int(m.group(2)))
    if any(p > 12 for p in first_parts):
        dayfirst = True
    elif any(p > 12 for p in second_parts):
        dayfirst = False
    ambiguous = bool(first_parts) and all(p <= 12 for p in first_parts + second_parts)
    slash = DATE_FORMATS_DAYFIRST if dayfirst else DATE_FORMATS_MONTHFIRST
    return DATE_FORMATS_YEAR_FIRST + DATE_FORMATS_NAMED + slash, ambiguous


def read_table(path):
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        try:
            import openpyxl
        except ImportError:
            sys.exit("Reading .xlsx needs openpyxl: pip install openpyxl (or export the sheet to CSV).")
        ws = openpyxl.load_workbook(path, read_only=True, data_only=True).active
        rows = [["" if c is None else str(c) for c in row] for row in ws.iter_rows(values_only=True)]
    else:
        with open(path, newline="", encoding="utf-8-sig") as f:
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            except csv.Error:
                dialect = csv.excel
            rows = list(csv.reader(f, dialect))
    if not rows:
        sys.exit(f"{path} is empty.")
    width = max(len(r) for r in rows)
    return [r + [""] * (width - len(r)) for r in rows]


def clean(rows, dayfirst=False):
    """Clean a table (first row = headers). Returns (headers, data, report_lines)."""
    report = []
    raw_headers, data = rows[0], rows[1:]
    original_rows = len(data)

    headers = unique_headers(raw_headers)
    renamed = [(a, b) for a, b in zip(raw_headers, headers) if a != b]
    if renamed:
        report.append("## Renamed columns")
        report += [f"- `{a}` → `{b}`" for a, b in renamed]

    missing_mapped = 0
    for row in data:
        for i, cell in enumerate(row):
            stripped = cell.strip()
            if stripped.lower() in MISSING_TOKENS:
                if stripped:
                    missing_mapped += 1
                row[i] = ""
            else:
                row[i] = re.sub(r"\s+", " ", stripped)

    data = [r for r in data if any(r)]
    empty_rows = original_rows - len(data)

    keep = [i for i in range(len(headers)) if any(r[i] for r in data)]
    dropped_cols = [headers[i] for i in range(len(headers)) if i not in keep]
    headers = [headers[i] for i in keep]
    data = [[r[i] for i in keep] for r in data]

    seen, deduped = set(), []
    for r in data:
        key = tuple(r)
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    duplicates = len(data) - len(deduped)
    data = deduped

    report.append("## Row and cell cleanup")
    report.append(f"- Rows in: {original_rows}, rows out: {len(data)}")
    report.append(f"- Fully empty rows removed: {empty_rows}")
    report.append(f"- Exact duplicate rows removed: {duplicates}")
    report.append(f"- Missing-value tokens (N/A, null, -, ...) blanked: {missing_mapped}")
    if dropped_cols:
        report.append(f"- Empty columns removed: {', '.join(f'`{c}`' for c in dropped_cols)}")

    report.append("## Column types")
    for col, name in enumerate(headers):
        values = [r[col] for r in data if r[col]]
        if not values:
            continue
        numbers = [parse_number(v) for v in values]
        if sum(n is not None for n in numbers) / len(values) >= INFER_THRESHOLD:
            bad = _apply(data, col, lambda v: _fmt_or_none(parse_number(v)))
            report.append(_type_line(name, "number", len(values), bad))
            continue
        formats, ambiguous = pick_date_formats(values, dayfirst)
        dates = [parse_date(v, formats) for v in values]
        if sum(d is not None for d in dates) / len(values) >= INFER_THRESHOLD:
            bad = _apply(data, col, lambda v: _iso_or_none(parse_date(v, formats)))
            line = _type_line(name, "date", len(values), bad)
            if ambiguous:
                order = "day-first" if formats[-1] in DATE_FORMATS_DAYFIRST else "month-first"
                line += f" ⚠️ every slash date was ambiguous; read as {order} (use --dayfirst to flip)"
            report.append(line)
            continue
        report.append(f"- `{name}`: text ({len(set(values))} distinct values)")

    return headers, data, report


def _fmt_or_none(num):
    return None if num is None else format_number(num)


def _iso_or_none(dt):
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d") if (dt.hour, dt.minute, dt.second) == (0, 0, 0) else dt.isoformat()


def _apply(data, col, convert):
    """Convert a column in place; return the values that could not be converted."""
    bad = []
    for r in data:
        if r[col]:
            out = convert(r[col])
            if out is None:
                bad.append(r[col])
            else:
                r[col] = out
    return bad


def _type_line(name, kind, count, bad):
    line = f"- `{name}`: {kind} ({count - len(bad)}/{count} normalized)"
    if bad:
        shown = ", ".join(f"`{b}`" for b in bad[:5]) + (" …" if len(bad) > 5 else "")
        line += f" — left unchanged, please review: {shown}"
    return line


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("input")
    p.add_argument("-o", "--output", help="cleaned CSV path (default: <input>_clean.csv)")
    p.add_argument("-r", "--report", help="Markdown report path (default: <input>_report.md)")
    p.add_argument("--dayfirst", action="store_true", help="read ambiguous dates like 03/04/2024 as 3 April")
    args = p.parse_args(argv)

    src = Path(args.input)
    out = Path(args.output or src.with_name(src.stem + "_clean.csv"))
    rep = Path(args.report or src.with_name(src.stem + "_report.md"))

    headers, data, report = clean(read_table(src), dayfirst=args.dayfirst)

    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(data)
    body = "\n".join(report).replace("\n## ", "\n\n## ")
    rep.write_text(f"# Cleaning report: {src.name}\n\n{body}\n", encoding="utf-8")
    print(f"Wrote {out} ({len(data)} rows) and {rep}")


if __name__ == "__main__":
    main()
