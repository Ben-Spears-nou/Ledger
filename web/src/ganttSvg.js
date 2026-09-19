// Draws the month-grid Gantt as a self-contained SVG so the whole chart can be
// copied or saved as one image for monthly reports.
import { progressColor } from "./progress.js";

// Kept quote-free so it stays valid inside an XML attribute.
const FONT = "Segoe UI, system-ui, sans-serif";
const LABEL_WIDTH = 250;
const PERCENT_WIDTH = 38;
const HEADER_HEIGHT = 24;
const LINE_HEIGHT = 13;
const ROW_PADDING = 11;
const CHAR_WIDTH = 5.6;
const MAX_LINES = 3;
const PAD = 8;
const TITLE_HEIGHT = 22;
const CAPTION_HEIGHT = 18;

const LANE_BAR = {
  remaining: "#2f6f9f",
  completed: "#3d6b54",
  behind: "#8a1f1f",
};

const LANE_PLANNED = {
  remaining: "#c7d3dc",
  completed: "#b8cbbf",
  behind: "#d9bcbc",
};

const INK = "#1b1f24";
const RULE = "#c9c1b2";
const MONTH_RULE = "#ddd8cb";
const HEADER_FILL = "#e6e0d4";
const ZEBRA_FILL = "#f4f1ea";

function escapeXml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function wrapLabel(text, maxChars) {
  const words = String(text).split(/\s+/).filter(Boolean);
  const lines = [];
  let line = "";
  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word;
    if (candidate.length > maxChars && line) {
      lines.push(line);
      line = word;
    } else {
      line = candidate;
    }
  }
  if (line) {
    lines.push(line);
  }
  if (!lines.length) {
    return [""];
  }
  if (lines.length > MAX_LINES) {
    const kept = lines.slice(0, MAX_LINES);
    kept[MAX_LINES - 1] = `${kept[MAX_LINES - 1].slice(0, Math.max(1, maxChars - 1))}…`;
    return kept;
  }
  return lines;
}

export function buildGanttSvg({ title, caption, columns, rows, asOfPct, tracked }) {
  const months = Math.max(columns.length, 1);
  const monthWidth = Math.max(22, Math.min(56, Math.round(640 / months)));
  const trackWidth = months * monthWidth;
  const percentWidth = tracked ? PERCENT_WIDTH : 0;
  const bodyLeft = LABEL_WIDTH + percentWidth;
  const gridWidth = bodyLeft + trackWidth;
  const maxChars = Math.floor((LABEL_WIDTH - 12) / CHAR_WIDTH);

  const gridTop = PAD + (title ? TITLE_HEIGHT : 0);
  const bodyTop = gridTop + HEADER_HEIGHT;

  let cursor = bodyTop;
  const laidOut = rows.map((row) => {
    const lines = wrapLabel(row.label, maxChars);
    const height = lines.length * LINE_HEIGHT + ROW_PADDING;
    const top = cursor;
    cursor += height;
    return { ...row, lines, top, height };
  });

  const bodyBottom = cursor;
  const width = gridWidth + PAD * 2;
  const height = bodyBottom + CAPTION_HEIGHT + PAD;

  const parts = [];
  parts.push(`<rect x="0" y="0" width="${width}" height="${height}" fill="#ffffff"/>`);

  if (title) {
    parts.push(
      `<text x="${PAD}" y="${PAD + 14}" font-family="${FONT}" font-size="13" font-weight="650" fill="${INK}">${escapeXml(title)}</text>`,
    );
  }

  // Row bands first so rules and bars paint over them.
  laidOut.forEach((row, index) => {
    if (index % 2 === 1) {
      parts.push(
        `<rect x="${PAD}" y="${row.top}" width="${gridWidth}" height="${row.height}" fill="${ZEBRA_FILL}"/>`,
      );
    }
  });

  parts.push(
    `<rect x="${PAD}" y="${gridTop}" width="${gridWidth}" height="${HEADER_HEIGHT}" fill="${HEADER_FILL}"/>`,
  );

  // Month columns.
  for (let index = 0; index < months; index += 1) {
    const x = PAD + bodyLeft + index * monthWidth;
    if (index > 0) {
      parts.push(
        `<line x1="${x}" y1="${gridTop}" x2="${x}" y2="${bodyBottom}" stroke="${MONTH_RULE}" stroke-width="1"/>`,
      );
    }
    parts.push(
      `<text x="${x + monthWidth / 2}" y="${gridTop + 16}" font-family="${FONT}" font-size="9.5" fill="${INK}" text-anchor="middle">${escapeXml(columns[index].label)}</text>`,
    );
  }

  parts.push(
    `<text x="${PAD + 6}" y="${gridTop + 16}" font-family="${FONT}" font-size="10" font-weight="650" fill="${INK}">Task</text>`,
  );
  if (tracked) {
    parts.push(
      `<text x="${PAD + bodyLeft - 6}" y="${gridTop + 16}" font-family="${FONT}" font-size="10" font-weight="650" fill="${INK}" text-anchor="end">%</text>`,
    );
  }

  // Rows: label, optional percent, bar.
  laidOut.forEach((row) => {
    parts.push(
      `<line x1="${PAD}" y1="${row.top}" x2="${PAD + gridWidth}" y2="${row.top}" stroke="${RULE}" stroke-width="1"/>`,
    );
    row.lines.forEach((line, lineIndex) => {
      parts.push(
        `<text x="${PAD + 6}" y="${row.top + 14 + lineIndex * LINE_HEIGHT}" font-family="${FONT}" font-size="11" fill="${INK}">${escapeXml(line)}</text>`,
      );
    });
    if (tracked) {
      const percent = row.percentBp === undefined || row.percentBp === null ? null : row.percentBp;
      if (percent !== null) {
        parts.push(
          `<text x="${PAD + bodyLeft - 6}" y="${row.top + 14}" font-family="${FONT}" font-size="10" fill="${INK}" text-anchor="end">${(percent / 100).toFixed(0)}%</text>`,
        );
      }
    }

    const barHeight = Math.max(8, row.height - 10);
    const barY = row.top + (row.height - barHeight) / 2;
    const barX = PAD + bodyLeft + (row.leftPct / 100) * trackWidth;
    const barWidth = Math.max(2, (row.widthPct / 100) * trackWidth);
    const isTracked = row.percentBp !== undefined && row.percentBp !== null;
    const planned = isTracked
      ? LANE_PLANNED[row.lane] || LANE_PLANNED.remaining
      : LANE_BAR[row.lane] || LANE_BAR.remaining;
    parts.push(
      `<rect x="${barX.toFixed(2)}" y="${barY.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${barHeight}" rx="2" fill="${planned}"/>`,
    );
    if (isTracked && row.percentBp > 0) {
      const fillWidth = Math.max(1, barWidth * (row.percentBp / 10000));
      parts.push(
        `<rect x="${barX.toFixed(2)}" y="${barY.toFixed(2)}" width="${fillWidth.toFixed(2)}" height="${barHeight}" rx="2" fill="${progressColor(row.percentBp)}"/>`,
      );
    }
  });

  // Column separators and the as-of marker sit above the bars.
  parts.push(
    `<line x1="${PAD + LABEL_WIDTH}" y1="${gridTop}" x2="${PAD + LABEL_WIDTH}" y2="${bodyBottom}" stroke="${RULE}" stroke-width="1"/>`,
  );
  if (tracked) {
    parts.push(
      `<line x1="${PAD + bodyLeft}" y1="${gridTop}" x2="${PAD + bodyLeft}" y2="${bodyBottom}" stroke="${RULE}" stroke-width="1"/>`,
    );
  }
  if (asOfPct !== null && asOfPct !== undefined) {
    const x = PAD + bodyLeft + (asOfPct / 100) * trackWidth;
    parts.push(
      `<line x1="${x.toFixed(2)}" y1="${bodyTop}" x2="${x.toFixed(2)}" y2="${bodyBottom}" stroke="#8a1f1f" stroke-width="1" stroke-dasharray="3 2"/>`,
    );
  }
  parts.push(
    `<rect x="${PAD}" y="${gridTop}" width="${gridWidth}" height="${bodyBottom - gridTop}" fill="none" stroke="${RULE}" stroke-width="1"/>`,
  );
  parts.push(
    `<line x1="${PAD}" y1="${bodyTop}" x2="${PAD + gridWidth}" y2="${bodyTop}" stroke="${RULE}" stroke-width="1"/>`,
  );

  if (caption) {
    parts.push(
      `<text x="${PAD}" y="${bodyBottom + 13}" font-family="${FONT}" font-size="10" fill="#5b5647">${escapeXml(caption)}</text>`,
    );
  }

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img">${parts.join("")}</svg>`;
  return { svg, width, height };
}
