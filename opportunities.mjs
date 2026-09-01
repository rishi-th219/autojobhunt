#!/usr/bin/env node
/**
 * opportunities.mjs — build output/opportunities.xlsx from scanner results.
 *
 * Four columns, exactly as requested:
 *   Company name | Job profile | Apply link | Posting date
 *
 * Sources (deduped by normalized URL, scan-history wins — it carries the
 * provider's structured posting date):
 *   1. data/scan-history.tsv  cols: url, first_seen, portal, title, company,
 *                             status, location, fingerprint, postedAt, trust*
 *   2. data/pipeline.md       "- [ ] {url} | {company} | {title} [| ... | posted: {date}]"
 *
 * Posting date: the provider's real posting date when it supplied one. Not every
 * ATS ships it, so rows without one fall back to the date the scanner FIRST SAW
 * the posting — rendered in grey italic to keep the two visually distinct. A
 * first-seen date means "posted on or before this", never "posted on this".
 *
 * Zero dependencies: the .xlsx is a ZIP of XML, written here with node's zlib.
 *
 * Usage:
 *   node opportunities.mjs                  # output/opportunities.xlsx
 *   node opportunities.mjs --out path.xlsx
 *   node opportunities.mjs --all            # include expired/skipped rows too
 *   node opportunities.mjs --days 30        # only postings dated within N days
 */

import { readFileSync, existsSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { deflateRawSync, crc32 as zlibCrc32 } from 'node:zlib';

const SCAN_HISTORY_PATH = 'data/scan-history.tsv';
const PIPELINE_PATH = 'data/pipeline.md';
const DEFAULT_OUT = 'output/opportunities.xlsx';

// ---------------------------------------------------------------- ZIP writer

// node >= 20.12 ships zlib.crc32; fall back to a table for older runtimes.
const crcTable = (() => {
  const t = new Int32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c;
  }
  return t;
})();

function crc32(buf) {
  if (typeof zlibCrc32 === 'function') return zlibCrc32(buf) >>> 0;
  let c = -1;
  for (let i = 0; i < buf.length; i++) c = crcTable[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ -1) >>> 0;
}

/** Minimal ZIP (deflate) writer — enough for the OOXML package. */
function zip(files) {
  const locals = [];
  const central = [];
  let offset = 0;

  for (const { name, data } of files) {
    const nameBuf = Buffer.from(name, 'utf-8');
    const raw = Buffer.isBuffer(data) ? data : Buffer.from(data, 'utf-8');
    const deflated = deflateRawSync(raw, { level: 9 });
    // Only pay the deflate overhead when it actually wins.
    const stored = deflated.length >= raw.length;
    const body = stored ? raw : deflated;
    const method = stored ? 0 : 8;
    const sum = crc32(raw);

    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);          // version needed
    local.writeUInt16LE(0x0800, 6);      // UTF-8 filename flag
    local.writeUInt16LE(method, 8);
    local.writeUInt16LE(0, 10);          // mod time
    local.writeUInt16LE(0x21, 12);       // mod date (1980-01-01)
    local.writeUInt32LE(sum, 14);
    local.writeUInt32LE(body.length, 18);
    local.writeUInt32LE(raw.length, 22);
    local.writeUInt16LE(nameBuf.length, 26);
    local.writeUInt16LE(0, 28);          // extra length
    locals.push(local, nameBuf, body);

    const cd = Buffer.alloc(46);
    cd.writeUInt32LE(0x02014b50, 0);
    cd.writeUInt16LE(20, 4);             // version made by
    cd.writeUInt16LE(20, 6);             // version needed
    cd.writeUInt16LE(0x0800, 8);
    cd.writeUInt16LE(method, 10);
    cd.writeUInt16LE(0, 12);
    cd.writeUInt16LE(0x21, 14);
    cd.writeUInt32LE(sum, 16);
    cd.writeUInt32LE(body.length, 20);
    cd.writeUInt32LE(raw.length, 24);
    cd.writeUInt16LE(nameBuf.length, 28);
    cd.writeUInt16LE(0, 30);             // extra
    cd.writeUInt16LE(0, 32);             // comment
    cd.writeUInt16LE(0, 34);             // disk
    cd.writeUInt16LE(0, 36);             // internal attrs
    cd.writeUInt32LE(0, 38);             // external attrs
    cd.writeUInt32LE(offset, 42);
    central.push(cd, nameBuf);

    offset += local.length + nameBuf.length + body.length;
  }

  const centralBuf = Buffer.concat(central);
  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(0, 4);
  eocd.writeUInt16LE(0, 6);
  eocd.writeUInt16LE(files.length, 8);
  eocd.writeUInt16LE(files.length, 10);
  eocd.writeUInt32LE(centralBuf.length, 12);
  eocd.writeUInt32LE(offset, 16);
  eocd.writeUInt16LE(0, 20);

  return Buffer.concat([...locals, centralBuf, eocd]);
}

// ---------------------------------------------------------------- XLSX build

function esc(s) {
  return String(s)
    .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g, '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Excel serial date (1900 system, with the 1900-leap-year quirk baked in). */
function excelSerial(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return null;
  const ms = Date.UTC(+m[1], +m[2] - 1, +m[3]);
  if (!Number.isFinite(ms)) return null;
  return Math.round((ms - Date.UTC(1899, 11, 30)) / 86400000);
}

const COLS = ['A', 'B', 'C', 'D'];
const HEADERS = ['Company name', 'Job profile', 'Apply link', 'Posting date'];

// Style ids, in the order they are declared in styles.xml below.
const S_HEADER = 1;
const S_LINK = 2;
const S_DATE = 3;
const S_DATE_APPROX = 4;

function textCell(ref, value, style) {
  const s = style ? ` s="${style}"` : '';
  return `<c r="${ref}"${s} t="inlineStr"><is><t xml:space="preserve">${esc(value)}</t></is></c>`;
}

function dateCell(ref, iso, approx) {
  const serial = excelSerial(iso);
  const style = approx ? S_DATE_APPROX : S_DATE;
  // Unparseable / missing dates degrade to text rather than a bogus serial.
  if (serial === null) return iso ? textCell(ref, iso, style) : `<c r="${ref}" s="${style}"/>`;
  return `<c r="${ref}" s="${style}"><v>${serial}</v></c>`;
}

function buildSheet(rows) {
  const lines = [];
  const hyperlinks = [];
  const rels = [];

  lines.push(
    `<row r="1" ht="20" customHeight="1">` +
      HEADERS.map((h, i) => textCell(`${COLS[i]}1`, h, S_HEADER)).join('') +
      `</row>`
  );

  rows.forEach((row, idx) => {
    const r = idx + 2;
    const cells = [
      textCell(`A${r}`, row.company),
      textCell(`B${r}`, row.title),
      textCell(`C${r}`, row.url, row.url ? S_LINK : 0),
      dateCell(`D${r}`, row.date, row.dateApprox),
    ];
    lines.push(`<row r="${r}">${cells.join('')}</row>`);

    if (row.url) {
      const rid = `rId${rels.length + 1}`;
      hyperlinks.push(`<hyperlink ref="C${r}" r:id="${rid}"/>`);
      rels.push(
        `<Relationship Id="${rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="${esc(row.url)}" TargetMode="External"/>`
      );
    }
  });

  const lastRow = rows.length + 1;
  const sheet =
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" ` +
    `xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">` +
    `<sheetPr><outlinePr summaryBelow="1" summaryRight="1"/></sheetPr>` +
    `<dimension ref="A1:D${Math.max(lastRow, 1)}"/>` +
    `<sheetViews><sheetView workbookViewId="0">` +
    `<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>` +
    `</sheetView></sheetViews>` +
    `<sheetFormatPr defaultRowHeight="15"/>` +
    `<cols>` +
    `<col min="1" max="1" width="30" customWidth="1"/>` +
    `<col min="2" max="2" width="52" customWidth="1"/>` +
    `<col min="3" max="3" width="62" customWidth="1"/>` +
    `<col min="4" max="4" width="14" customWidth="1"/>` +
    `</cols>` +
    `<sheetData>${lines.join('')}</sheetData>` +
    `<autoFilter ref="A1:D${Math.max(lastRow, 1)}"/>` +
    (hyperlinks.length ? `<hyperlinks>${hyperlinks.join('')}</hyperlinks>` : '') +
    `</worksheet>`;

  return { sheet, rels };
}

const STYLES =
  `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
  `<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">` +
  `<numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy\\-mm\\-dd"/></numFmts>` +
  `<fonts count="4">` +
  `<font><sz val="11"/><name val="Calibri"/></font>` +
  `<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>` +
  `<font><u/><sz val="11"/><color rgb="FF0563C1"/><name val="Calibri"/></font>` +
  `<font><i/><sz val="11"/><color rgb="FF808080"/><name val="Calibri"/></font>` +
  `</fonts>` +
  `<fills count="3">` +
  `<fill><patternFill patternType="none"/></fill>` +
  `<fill><patternFill patternType="gray125"/></fill>` +
  `<fill><patternFill patternType="solid"><fgColor rgb="FF2F5597"/><bgColor indexed="64"/></patternFill></fill>` +
  `</fills>` +
  `<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>` +
  `<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>` +
  `<cellXfs count="5">` +
  `<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>` +
  `<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="center"/></xf>` +
  `<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>` +
  `<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>` +
  `<xf numFmtId="164" fontId="3" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyFont="1"/>` +
  `</cellXfs>` +
  `<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>` +
  `</styleSheet>`;

function buildWorkbook(rows) {
  const { sheet, rels } = buildSheet(rows);
  return zip([
    {
      name: '[Content_Types].xml',
      data:
        `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
        `<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">` +
        `<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>` +
        `<Default Extension="xml" ContentType="application/xml"/>` +
        `<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>` +
        `<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>` +
        `<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>` +
        `</Types>`,
    },
    {
      name: '_rels/.rels',
      data:
        `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
        `<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">` +
        `<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>` +
        `</Relationships>`,
    },
    {
      name: 'xl/workbook.xml',
      data:
        `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
        `<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" ` +
        `xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">` +
        `<sheets><sheet name="Opportunities" sheetId="1" r:id="rId1"/></sheets>` +
        `</workbook>`,
    },
    {
      name: 'xl/_rels/workbook.xml.rels',
      data:
        `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
        `<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">` +
        `<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>` +
        `<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>` +
        `</Relationships>`,
    },
    { name: 'xl/styles.xml', data: STYLES },
    { name: 'xl/worksheets/sheet1.xml', data: sheet },
    {
      name: 'xl/worksheets/_rels/sheet1.xml.rels',
      data:
        `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
        `<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">` +
        `${rels.join('')}</Relationships>`,
    },
  ]);
}

// ---------------------------------------------------------------- collection

/** Same normalization the scanner dedups on: strip tracking params + trailing slash. */
function normalizeUrl(url) {
  const raw = String(url || '').trim();
  if (!raw) return '';
  try {
    const u = new URL(raw);
    for (const p of [...u.searchParams.keys()]) {
      if (/^(utm_|gh_src|ref|source|src)/i.test(p)) u.searchParams.delete(p);
    }
    u.hash = '';
    let out = u.toString();
    if (out.endsWith('/')) out = out.slice(0, -1);
    return out;
  } catch {
    return raw.replace(/\/+$/, '');
  }
}

function readScanHistory({ includeAll }) {
  if (!existsSync(SCAN_HISTORY_PATH)) return [];
  const out = [];
  const lines = readFileSync(SCAN_HISTORY_PATH, 'utf-8').split('\n');
  for (const line of lines) {
    if (!line.trim()) continue;
    const c = line.split('\t');
    if (c[0] === 'url') continue; // header
    const [url, firstSeen, , title, company, status] = c;
    if (!url) continue;
    if (!includeAll && status !== 'added') continue;
    const postedAt = (c[8] || '').trim();
    out.push({
      url: url.trim(),
      company: (company || '').trim(),
      title: (title || '').trim(),
      date: postedAt || (firstSeen || '').trim(),
      dateApprox: !postedAt,
    });
  }
  return out;
}

function readPipeline() {
  if (!existsSync(PIPELINE_PATH)) return [];
  const out = [];
  for (const line of readFileSync(PIPELINE_PATH, 'utf-8').split('\n')) {
    const m = /^\s*-\s*\[[ xX]\]\s*(.+)$/.exec(line);
    if (!m) continue;
    const parts = m[1].split('|').map((p) => p.trim());
    const url = parts[0];
    if (!/^https?:\/\//i.test(url)) continue;
    // posted: rides as a labeled segment anywhere after the positional cells.
    const postedSeg = parts.find((p) => /^posted:\s*/i.test(p));
    const posted = postedSeg ? postedSeg.replace(/^posted:\s*/i, '').trim() : '';
    out.push({
      url,
      company: parts[1] || '',
      title: parts[2] || '',
      date: posted,
      dateApprox: false,
    });
  }
  return out;
}

function collect({ includeAll, days }) {
  const seen = new Map();
  // scan-history first — it carries the provider's structured posting date.
  for (const row of [...readScanHistory({ includeAll }), ...readPipeline()]) {
    const key = normalizeUrl(row.url);
    if (!key) continue;
    const prev = seen.get(key);
    if (!prev) {
      seen.set(key, row);
      continue;
    }
    // Let a later source fill in blanks the first one left empty.
    if (!prev.company && row.company) prev.company = row.company;
    if (!prev.title && row.title) prev.title = row.title;
    if (prev.dateApprox && row.date && !row.dateApprox) {
      prev.date = row.date;
      prev.dateApprox = false;
    }
  }

  let rows = [...seen.values()];

  if (days > 0) {
    const cutoff = Date.now() - days * 86400000;
    rows = rows.filter((r) => {
      const t = Date.parse(r.date);
      return Number.isFinite(t) ? t >= cutoff : true; // no date → don't penalize
    });
  }

  // Newest first; undated rows sink to the bottom, then alphabetical by company.
  rows.sort((a, b) => {
    const ta = Date.parse(a.date);
    const tb = Date.parse(b.date);
    const va = Number.isFinite(ta) ? ta : -Infinity;
    const vb = Number.isFinite(tb) ? tb : -Infinity;
    if (va !== vb) return vb - va;
    return a.company.localeCompare(b.company);
  });

  return rows;
}

// ---------------------------------------------------------------------- main

function main() {
  const args = process.argv.slice(2);
  const includeAll = args.includes('--all');
  const outArg = args.find((a) => a.startsWith('--out'));
  const out = outArg ? (outArg.split('=')[1] || args[args.indexOf(outArg) + 1] || DEFAULT_OUT) : DEFAULT_OUT;
  const daysArg = args.find((a) => a.startsWith('--days'));
  const days = daysArg ? Number(daysArg.split('=')[1] || args[args.indexOf(daysArg) + 1] || 0) : 0;

  const rows = collect({ includeAll, days: Number.isFinite(days) ? days : 0 });

  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, buildWorkbook(rows));

  const approx = rows.filter((r) => r.dateApprox).length;
  console.log(JSON.stringify({
    status: 'ok',
    out,
    rows: rows.length,
    exact_posting_dates: rows.length - approx,
    first_seen_fallback: approx,
    sources: {
      'scan-history.tsv': existsSync(SCAN_HISTORY_PATH),
      'pipeline.md': existsSync(PIPELINE_PATH),
    },
  }, null, 2));

  if (rows.length === 0) {
    console.log('\nNo opportunities yet — run `node scan.mjs` first to populate data/scan-history.tsv.');
  }
}

main();
