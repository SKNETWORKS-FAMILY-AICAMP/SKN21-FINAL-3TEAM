/**
 * 5주차 산출물 공통 모듈
 * 각 산출물 PDF 예시 레이아웃에 맞는 빌딩블록 제공
 */
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel,
  BorderStyle, WidthType, ShadingType, PageNumber, PageBreak,
} = require("docx");
const fs = require("fs");
const path = require("path");

const PAGE_W = 9072;
const THIN = { style: BorderStyle.SINGLE, size: 1, color: "BBBBBB" };
const NONE = { style: BorderStyle.NONE, size: 0 };

function t(text, opts = {}) {
  return new TextRun({
    text, font: opts.font || "맑은 고딕",
    size: opts.size || 20,
    bold: !!opts.bold,
    italics: !!opts.italic,
    underline: opts.underline ? {} : undefined,
    color: opts.color,
  });
}

function para(runs, opts = {}) {
  if (typeof runs === "string") runs = [t(runs, opts)];
  return new Paragraph({
    spacing: { after: opts.after ?? 80, before: opts.before ?? 0, line: opts.line },
    alignment: opts.align || AlignmentType.LEFT,
    indent: opts.indent ? { left: opts.indent } : undefined,
    children: runs,
  });
}

// 공통 헤더 배너 (산출물 1,2,3,5)
function commonHeader(docName) {
  return [
    new Paragraph({
      spacing: { before: 200, after: 0 },
      alignment: AlignmentType.CENTER,
      shading: { fill: "EDF2FA", type: ShadingType.CLEAR },
      children: [t("SK네트웍스 Family AI과정 21기", { bold: true, size: 22 })],
    }),
    new Paragraph({
      spacing: { before: 60, after: 100 },
      alignment: AlignmentType.CENTER,
      shading: { fill: "EDF2FA", type: ShadingType.CLEAR },
      children: [
        t("모델링 및 평가 ", { bold: true, size: 36, color: "2F5496" }),
        t(docName, { bold: true, size: 36, color: "000000" }),
      ],
    }),
    para("", { after: 200 }),
  ];
}

// 개요 블록
function overviewBlock(opts) {
  return [
    para([t("개요", { bold: true, size: 22, underline: true })], { after: 120 }),
    bullet("산출물 단계 : " + opts.step),
    bullet("평가 산출물 : " + opts.docName),
    bullet("제출 일자 : " + opts.date),
    bullet("깃허브 경로 : " + opts.github),
    bullet("작성 팀원 : " + opts.members),
    para("", { after: 200 }),
  ];
}

function h1(text) {
  return new Paragraph({
    spacing: { before: 400, after: 200 },
    children: [t(text, { bold: true, size: 32 })],
  });
}

function h2(text) {
  return new Paragraph({
    spacing: { before: 300, after: 140 },
    children: [t(text, { bold: true, size: 24 })],
  });
}

function h3(text) {
  return new Paragraph({
    spacing: { before: 200, after: 100 },
    children: [t(text, { bold: true, size: 22 })],
  });
}

function body(text, opts = {}) {
  return para([t(text, { size: 20, bold: opts.bold, color: opts.color })], {
    after: opts.after || 80, indent: opts.indent, align: opts.align,
  });
}

function bullet(text, level = 0) {
  const prefix = level === 0 ? "  \u25CF " : "      \u25CB ";
  return para([t(prefix + text, { size: 20 })], { after: 40 });
}

function dash(text, indent = 0) {
  const pad = "    ".repeat(indent);
  return para([t(pad + "- " + text, { size: 20 })], { after: 40 });
}

function numbered(num, text) {
  return para([t("  " + num + ". ", { bold: true, size: 20 }), t(text, { size: 20 })], { after: 50 });
}

// 2단 테이블 행
function twoColRow(label, contentChildren, opts = {}) {
  const labelW = opts.labelW || 2000;
  const contentW = opts.contentW || (PAGE_W - labelW);
  const topBorder = opts.topBorder || { style: BorderStyle.SINGLE, size: 4, color: "999999" };
  const btmBorder = opts.btmBorder || THIN;
  const border = { style: BorderStyle.SINGLE, size: 1, color: "BBBBBB" };
  return new Table({
    width: { size: PAGE_W, type: WidthType.DXA },
    columnWidths: [labelW, contentW],
    rows: [new TableRow({
      children: [
        new TableCell({
          width: { size: labelW, type: WidthType.DXA },
          margins: { top: 100, bottom: 100, left: 120, right: 80 },
          borders: { top: border, bottom: border, left: border, right: border },
          shading: opts.labelBg ? { fill: opts.labelBg, type: ShadingType.CLEAR } : { fill: "F5F5F5", type: ShadingType.CLEAR },
          verticalAlign: "center",
          children: [para([t(label, { bold: true, size: 19, color: "333333" })], { align: AlignmentType.CENTER })],
        }),
        new TableCell({
          width: { size: contentW, type: WidthType.DXA },
          margins: { top: 100, bottom: 100, left: 160, right: 120 },
          borders: { top: border, bottom: border, left: border, right: border },
          children: contentChildren,
        }),
      ]
    })],
  });
}

// 정보 테이블 (LLM 활용 소프트웨어)
function infoTable(rows) {
  const border = { style: BorderStyle.SINGLE, size: 1, color: "999999" };
  const borders = { top: border, bottom: border, left: border, right: border };
  return new Table({
    width: { size: PAGE_W, type: WidthType.DXA },
    columnWidths: [2000, PAGE_W - 2000],
    rows: rows.map(([label, value]) => new TableRow({
      children: [
        new TableCell({
          width: { size: 2000, type: WidthType.DXA }, borders,
          margins: { top: 60, bottom: 60, left: 100, right: 100 },
          shading: { fill: "F5F5F5", type: ShadingType.CLEAR },
          verticalAlign: "center",
          children: [para([t(label, { bold: true, size: 19 })], { align: AlignmentType.CENTER })],
        }),
        new TableCell({
          width: { size: PAGE_W - 2000, type: WidthType.DXA }, borders,
          margins: { top: 60, bottom: 60, left: 120, right: 100 },
          children: [para([t(value, { size: 19 })])],
        }),
      ]
    })),
  });
}

// 데이터 테이블
function dataTable(headers, rows, colWidths) {
  const hdrBg = { fill: "F0F0F0", type: ShadingType.CLEAR };
  const border = { style: BorderStyle.SINGLE, size: 1, color: "BBBBBB" };
  const borders = { top: border, bottom: border, left: border, right: border };
  function mkCell(text, w, opts = {}) {
    return new TableCell({
      width: { size: w, type: WidthType.DXA }, borders,
      margins: { top: 50, bottom: 50, left: 80, right: 80 },
      shading: opts.bg || undefined,
      verticalAlign: "center",
      children: [para([t(String(text), { size: 18, bold: opts.bold })], { align: opts.align || AlignmentType.CENTER })],
    });
  }
  const totalW = colWidths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: totalW, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [
      new TableRow({ children: headers.map((h, i) => mkCell(h, colWidths[i], { bold: true, bg: hdrBg })) }),
      ...rows.map(row => new TableRow({ children: row.map((cell, i) => mkCell(cell, colWidths[i])) })),
    ],
  });
}

function codeBlock(lines) {
  if (typeof lines === "string") lines = lines.split("\n");
  return lines.map(line => new Paragraph({
    shading: { fill: "2D2D2D", type: ShadingType.CLEAR },
    spacing: { after: 0, before: 0, line: 276 },
    children: [t(line || " ", { font: "Consolas", size: 16, color: "D4D4D4" })],
  }));
}

function codeBlockLight(lines) {
  if (typeof lines === "string") lines = lines.split("\n");
  return lines.map(line => new Paragraph({
    shading: { fill: "F5F5F5", type: ShadingType.CLEAR },
    spacing: { after: 0, before: 0, line: 276 },
    indent: { left: 200 },
    children: [t(line || " ", { font: "Consolas", size: 17 })],
  }));
}

function treeBlock(lines) {
  return lines.map(line => new Paragraph({
    shading: { fill: "F8F8F8", type: ShadingType.CLEAR },
    spacing: { after: 0, line: 280 },
    children: [t(line, { font: "Consolas", size: 17 })],
  }));
}

function pgBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

function imagePlaceholder(label) {
  return new Paragraph({
    spacing: { before: 200, after: 200 },
    alignment: AlignmentType.CENTER,
    shading: { fill: "E0E0E0", type: ShadingType.CLEAR },
    children: [t("[" + label + "]", { size: 22, color: "666666", italic: true })],
  });
}

function buildDoc(children) {
  return new Document({
    styles: { default: { document: { run: { font: "맑은 고딕", size: 20 } } } },
    numbering: { config: [] },
    sections: [{
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1200, right: 1400, bottom: 1000, left: 1400 },
        },
      },
      footers: {
        default: new Footer({
          children: [para([
            t("SKN21-FINAL-3TEAM | WorkFlow Agent", { size: 14, color: "AAAAAA" }),
            t("    - ", { size: 14, color: "AAAAAA" }),
            new TextRun({ children: [PageNumber.CURRENT], font: "맑은 고딕", size: 14, color: "AAAAAA" }),
            t(" -", { size: 14, color: "AAAAAA" }),
          ], { align: AlignmentType.CENTER })],
        }),
      },
      children,
    }],
  });
}

function save(doc, outPath) {
  const BASE = path.resolve(__dirname, "..", "..");
  const fullPath = path.resolve(BASE, outPath);
  const dir = path.dirname(fullPath);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  return Packer.toBuffer(doc).then(buf => {
    fs.writeFileSync(fullPath, buf);
    console.log("Created: " + fullPath + " (" + (buf.length / 1024).toFixed(1) + "KB)");
  });
}

module.exports = {
  t, para, commonHeader, overviewBlock,
  h1, h2, h3, body, bullet, dash, numbered,
  twoColRow, infoTable, dataTable,
  codeBlock, codeBlockLight, treeBlock,
  pgBreak, imagePlaceholder, buildDoc, save,
  PAGE_W, PageBreak, Paragraph, TextRun, AlignmentType,
  Table, TableRow, TableCell, BorderStyle, WidthType, ShadingType,
};
