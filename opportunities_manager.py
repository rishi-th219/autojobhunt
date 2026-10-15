#!/usr/bin/env python3
"""
opportunities_manager.py — Manages opportunities.xlsx with the 7 canonical columns:
  1. Firm name
  2. Job role
  3. apply link
  4. experience required
  5. top skills required
  6. pay
  7. job location

Generates a fully compliant OpenXML Excel spreadsheet (.xlsx) with styled headers,
clickable hyperlinks, and proper column widths using only Python's standard library (zipfile + xml).
Also syncs opportunities.csv and can be called directly or imported by daily_job_scanner.py.
"""

import os
import sys
import csv
import json
import re
import io
import zipfile
from xml.sax.saxutils import escape

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
XLSX_FILE = os.path.join(PROJECT_ROOT, "opportunities.xlsx")
CSV_FILE = os.path.join(PROJECT_ROOT, "opportunities.csv")
JSON_FILE = os.path.join(PROJECT_ROOT, "new_jobs_found.json")
PIPELINE_FILE = os.path.join(PROJECT_ROOT, "data", "pipeline.md")

COLUMNS = [
    "Firm name",
    "Job role",
    "apply link",
    "experience required",
    "top skills required",
    "pay",
    "job location"
]

def clean_text(s):
    if s is None:
        return ""
    # Remove control characters that violate XML 1.0
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(s)).strip()

import config_loader

def is_valid_location(location):
    return config_loader.is_valid_location(location)

def is_valid_role(title):
    return config_loader.is_valid_role(title)




def build_xlsx(rows, output_path=XLSX_FILE):
    """
    Builds a standard OpenXML (.xlsx) file in memory and writes to disk.
    Zero external dependencies — pure zipfile + OpenXML.
    """
    buf = io.BytesIO()

    # Calculate column widths based on data length
    col_widths = {i: len(COLUMNS[i]) + 4 for i in range(len(COLUMNS))}
    for row in rows:
        for i, col_name in enumerate(COLUMNS):
            val = str(row.get(col_name, ""))
            if len(val) > col_widths[i]:
                col_widths[i] = min(max(len(val) + 3, col_widths[i]), 65)

    # 1. Sheet XML & Hyperlinks
    sheet_rows_xml = []
    hyperlinks_xml = []
    rels_xml = []

    # Header Row (Row 1) — Style 1 (Bold, Dark Navy header, White text)
    header_cells = []
    for i, col_name in enumerate(COLUMNS):
        col_letter = chr(65 + i)
        header_cells.append(f'<c r="{col_letter}1" t="inlineStr" s="1"><is><t>{escape(col_name)}</t></is></c>')
    sheet_rows_xml.append(f'<row r="1" ht="26" customHeight="1">{"".join(header_cells)}</row>')

    # Data Rows
    for r_idx, row in enumerate(rows, start=2):
        cells = []
        for c_idx, col_name in enumerate(COLUMNS):
            col_letter = chr(65 + c_idx)
            val = clean_text(row.get(col_name, ""))

            # Apply link column (Column C) — clickable hyperlink with style 2
            if col_name == "apply link" and val.startswith("http"):
                rid = f"rId{len(rels_xml) + 1}"
                rels_xml.append(
                    f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
                    f'Target="{escape(val)}" TargetMode="External"/>'
                )
                hyperlinks_xml.append(f'<hyperlink ref="{col_letter}{r_idx}" r:id="{rid}"/>')
                cells.append(f'<c r="{col_letter}{r_idx}" t="inlineStr" s="2"><is><t>{escape(val)}</t></is></c>')
            else:
                cells.append(f'<c r="{col_letter}{r_idx}" t="inlineStr"><is><t>{escape(val)}</t></is></c>')

        sheet_rows_xml.append(f'<row r="{r_idx}">{"".join(cells)}</row>')

    # Column definition XML
    cols_xml = []
    for i in range(len(COLUMNS)):
        col_idx = i + 1
        width = col_widths[i]
        cols_xml.append(f'<col min="{col_idx}" max="{col_idx}" width="{width}" customWidth="1"/>')

    hyperlinks_tag = f'<hyperlinks>{"".join(hyperlinks_xml)}</hyperlinks>' if hyperlinks_xml else ""

    sheet_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" 
           xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheetViews><sheetView tabSelected="1" workbookViewId="0"/></sheetViews>
  <sheetFormatPr defaultRowHeight="18"/>
  <cols>{"".join(cols_xml)}</cols>
  <sheetData>{"".join(sheet_rows_xml)}</sheetData>
  {hyperlinks_tag}
</worksheet>"""

    sheet_rels_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {"".join(rels_xml)}
</Relationships>"""

    styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="3">
    <font><name val="Segoe UI"/><sz val="10"/><color rgb="FF333333"/></font>
    <font><b/><name val="Segoe UI"/><sz val="11"/><color rgb="FFFFFFFF"/></font>
    <font><u/><name val="Segoe UI"/><sz val="10"/><color rgb="FF0066CC"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1F497D"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color rgb="FFD9D9D9"/></left>
      <right style="thin"><color rgb="FFD9D9D9"/></right>
      <top style="thin"><color rgb="FFD9D9D9"/></top>
      <bottom style="thin"><color rgb="FFD9D9D9"/></bottom>
    </border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="3">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
      <alignment vertical="center"/>
    </xf>
    <xf numFmtId="0" fontId="2" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1"/>
  </cellXfs>
</styleSheet>"""

    workbook_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" 
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Opportunities" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>"""

    workbook_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

    dot_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

    content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types_xml)
        z.writestr("_rels/.rels", dot_rels)
        z.writestr("xl/workbook.xml", workbook_xml)
        z.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        z.writestr("xl/styles.xml", styles_xml)
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        if rels_xml:
            z.writestr("xl/worksheets/_rels/sheet1.xml.rels", sheet_rels_xml)

    with open(output_path, "wb") as f:
        f.write(buf.getvalue())

REJECTED_URLS, KNOWN_CORRECTIONS = config_loader.get_corrections()


def sort_key(row):
    exp = row.get("experience required", "").lower()
    role = row.get("Job role", "").lower()
    if "0-1" in exp or "0 to 1" in exp:
        return (0, row.get("Firm name", ""))
    elif "0-2" in exp or "0 to 2" in exp or "early career" in exp or "associate" in exp or "entry" in exp:
        return (1, row.get("Firm name", ""))
    elif "1-2" in exp or "1 to 2" in exp or "1+" in exp:
        return (2, row.get("Firm name", ""))
    elif any(k in role for k in ["ml engineer", "machine learning", "data scientist", "deep learning", "ai engineer", "research", "r&d", "applied ai", "applied scientist", "jrf", "srf", "project associate", "assistant professor", "lecturer"]):
        return (3, row.get("Firm name", ""))
    elif "1-3" in exp or "1 to 3" in exp:
        return (4, row.get("Firm name", ""))
    elif "2-3" in exp or "2 to 3" in exp or "2-4" in exp:
        return (5, row.get("Firm name", ""))
    else:
        return (6, row.get("Firm name", ""))

def load_existing_opportunities():
    seen_urls = set()
    opportunities = []

    # Dynamically populate REJECTED_URLS from archived expired jobs
    archived_csv = os.path.join(PROJECT_ROOT, "data", "archived_expired_opportunities.csv")
    if os.path.exists(archived_csv):
        try:
            with open(archived_csv, "r", encoding="utf-8", errors="ignore") as f:
                arch_reader = csv.DictReader(f)
                for a_row in arch_reader:
                    a_url = a_row.get("apply link", "").strip()
                    if a_url:
                        REJECTED_URLS.add(a_url)
                        REJECTED_URLS.add(a_url.split("#")[0].rstrip("/"))
        except Exception:
            pass

    # 1. From opportunities.csv
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get("apply link", "").strip()
                comp = row.get("Firm name", "").strip()
                role = row.get("Job role", "").strip()
                loc = row.get("job location", "").strip()
                if any(b in (comp + " " + url).lower() for b in ["amazon", "adci", "asspl", "amazon.jobs"]):
                    continue
                if not is_valid_location(loc) or not is_valid_role(role):
                    continue
                norm = url.split("#")[0].rstrip("/")
                row_data = {k: row.get(k, "") for k in COLUMNS}
                if norm in KNOWN_CORRECTIONS:
                    row_data.update(KNOWN_CORRECTIONS[norm])
                elif url in KNOWN_CORRECTIONS:
                    row_data.update(KNOWN_CORRECTIONS[url])
                if norm not in REJECTED_URLS and url not in REJECTED_URLS:
                    seen_urls.add(norm)
                    opportunities.append(row_data)

    # 2. From new_jobs_found.json
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
                for item in data:
                    url = item.get("apply link", "").strip()
                    comp = item.get("Firm name", "").strip()
                    role = item.get("Job role", "Data Analyst")
                    loc = item.get("job location", "Bengaluru, IND")
                    if any(b in (comp + " " + url).lower() for b in ["amazon", "adci", "asspl", "amazon.jobs"]):
                        continue
                    if not is_valid_location(loc) or not is_valid_role(role):
                        continue
                    norm = url.split("#")[0].rstrip("/")
                    if norm and norm not in seen_urls and norm not in REJECTED_URLS and url not in REJECTED_URLS:
                        seen_urls.add(norm)
                        row_data = {
                            "Firm name": comp,
                            "Job role": role,
                            "apply link": url,
                            "experience required": item.get("experience required", "0-2 years (Inferred)"),
                            "top skills required": item.get("top skills required", "SQL, Power BI, Excel"),
                            "pay": item.get("pay", "Not Listed"),
                            "job location": loc
                        }
                        if norm in KNOWN_CORRECTIONS:
                            row_data.update(KNOWN_CORRECTIONS[norm])
                        elif url in KNOWN_CORRECTIONS:
                            row_data.update(KNOWN_CORRECTIONS[url])
                        opportunities.append(row_data)
        except Exception:
            pass

    # 3. From data/pipeline.md
    if os.path.exists(PIPELINE_FILE):
        with open(PIPELINE_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line.startswith("- ["):
                    continue
                m = re.search(r"https?://[^\s\|]+", line)
                if not m:
                    continue
                url = m.group(0)
                if "amazon.jobs" in url.lower():
                    continue
                norm = url.split("#")[0].rstrip("/")
                if norm in seen_urls or norm in REJECTED_URLS or url in REJECTED_URLS:
                    continue

                parts = [p.strip() for p in line.split("|")]
                company = "Unknown"
                title = "Data Analyst"
                loc = "Bengaluru, India"

                if len(parts) >= 3:
                    company = parts[1]
                    title = parts[2]
                if any(b in (company + " " + title).lower() for b in ["amazon", "adci", "asspl"]):
                    continue
                if len(parts) >= 4 and "posted:" not in parts[3] and "exp:" not in parts[3]:
                    loc = parts[3]
                if not is_valid_location(loc) or not is_valid_role(title):
                    continue
                seen_urls.add(norm)

                # Infer skills from title
                skills = ["SQL", "Excel"]
                t_lower = title.lower()
                if "power bi" in t_lower or "bi" in t_lower:
                    skills.append("Power BI")
                if "python" in t_lower:
                    skills.append("Python")
                if "tableau" in t_lower:
                    skills.append("Tableau")
                if "reporting" in t_lower:
                    skills.append("Reporting")
                if "etl" in t_lower:
                    skills.append("ETL")
                if any(k in t_lower for k in ["machine learning", "ml engineer", "data scientist", "deep learning", "ai engineer", "applied ml"]):
                    skills.extend(["PyTorch", "Deep Learning", "Scikit-Learn"])
                if any(k in t_lower for k in ["generative ai", "genai", "llm", "diffusion", "nlp", "vision"]):
                    skills.extend(["Generative AI", "LLMs", "Transformers", "PyTorch"])
                if "professor" in t_lower or "lecturer" in t_lower or "faculty" in t_lower:
                    skills.extend(["Algorithms", "DBMS", "Curriculum Instruction"])
                if "jrf" in t_lower or "fellow" in t_lower or "project associate" in t_lower:
                    skills.extend(["Deep Learning", "PyTorch", "Research Benchmarking"])

                row_data = {
                    "Firm name": company,
                    "Job role": title,
                    "apply link": url,
                    "experience required": "0-2 years (Inferred)",
                    "top skills required": ", ".join(skills),
                    "pay": "Not Listed",
                    "job location": loc
                }
                if norm in KNOWN_CORRECTIONS:
                    row_data.update(KNOWN_CORRECTIONS[norm])
                elif url in KNOWN_CORRECTIONS:
                    row_data.update(KNOWN_CORRECTIONS[url])
                opportunities.append(row_data)

    opportunities.sort(key=sort_key)
    return opportunities

def save_all_opportunities(opportunities):
    # 1. Save XLSX
    build_xlsx(opportunities, XLSX_FILE)

    # 2. Save CSV
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for opp in opportunities:
            writer.writerow({k: opp.get(k, "") for k in COLUMNS})

    # 3. Save JSON
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(opportunities, f, indent=2, ensure_ascii=False)

def add_new_opportunities(new_jobs):
    """
    Called by daily_job_scanner.py to append new jobs.
    new_jobs is a list of dicts with keys: url, company, title, location, date
    """
    existing = load_existing_opportunities()
    seen = {clean_text(o.get("apply link", "")).split("#")[0].rstrip("/") for o in existing}

    added = 0
    for job in new_jobs:
        url = job.get("url", "").strip()
        norm = url.split("#")[0].rstrip("/")
        if not norm or norm in seen or norm in REJECTED_URLS or url in REJECTED_URLS:
            continue
        seen.add(norm)

        title = job.get("title", "Data Analyst")
        company = job.get("company", "Discovered Company")
        loc = job.get("location", "Bengaluru, IND")
        if not is_valid_location(loc) or not is_valid_role(title):
            continue

        skills = ["SQL", "Excel"]
        t_lower = title.lower()
        if "power bi" in t_lower or "bi" in t_lower:
            skills.append("Power BI")
        if "python" in t_lower:
            skills.append("Python")
        if "tableau" in t_lower:
            skills.append("Tableau")
        if "etl" in t_lower:
            skills.append("ETL")
        if any(k in t_lower for k in ["machine learning", "ml engineer", "data scientist", "deep learning", "ai engineer", "applied ml"]):
            skills.extend(["PyTorch", "Deep Learning", "Scikit-Learn"])
        if any(k in t_lower for k in ["generative ai", "genai", "llm", "diffusion", "nlp", "vision"]):
            skills.extend(["Generative AI", "LLMs", "Transformers", "PyTorch"])
        if "professor" in t_lower or "lecturer" in t_lower or "faculty" in t_lower:
            skills.extend(["Algorithms", "DBMS", "Curriculum Instruction"])
        if "jrf" in t_lower or "fellow" in t_lower or "project associate" in t_lower:
            skills.extend(["Deep Learning", "PyTorch", "Research Benchmarking"])
        if "reporting" in t_lower:
            skills.append("Reporting")

        row_data = {
            "Firm name": company,
            "Job role": title,
            "apply link": url,
            "experience required": "0-2 years (Inferred)",
            "top skills required": ", ".join(skills),
            "pay": "Not Listed",
            "job location": loc
        }
        if norm in KNOWN_CORRECTIONS:
            row_data.update(KNOWN_CORRECTIONS[norm])
        elif url in KNOWN_CORRECTIONS:
            row_data.update(KNOWN_CORRECTIONS[url])

        existing.append(row_data)
        added += 1

    if added > 0:
        existing.sort(key=sort_key)
        save_all_opportunities(existing)
        print(f"Added {added} new opportunities to {XLSX_FILE} and {CSV_FILE}.")

    return added

def main():
    print("Loading and consolidating all opportunities...")
    opps = load_existing_opportunities()
    print(f"Total unique opportunities consolidated: {len(opps)}")
    save_all_opportunities(opps)
    print(f"✓ Successfully wrote {len(opps)} opportunities to {XLSX_FILE} and {CSV_FILE}.")

if __name__ == "__main__":
    main()
