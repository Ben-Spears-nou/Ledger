import { useMemo, useState } from "react";
import { buildGanttSvg } from "../ganttSvg.js";
import { barSpan, dateOffsetPct, monthColumns } from "../monthGrid.js";

async function rasterize(image, dataUrl, scale = 2) {
  const element = new Image();
  element.src = dataUrl;
  await element.decode();
  const canvas = document.createElement("canvas");
  canvas.width = image.width * scale;
  canvas.height = image.height * scale;
  const context = canvas.getContext("2d");
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.setTransform(scale, 0, 0, scale, 0, 0);
  context.drawImage(element, 0, 0);
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("could not render the chart"))),
      "image/png",
    );
  });
}

export function MonthGantt({ chart, rows, empty, title }) {
  const [notice, setNotice] = useState("");
  const image = useMemo(() => {
    if (!chart?.chart_start || !chart?.chart_end || !rows?.length) {
      return null;
    }
    const columns = monthColumns(chart.chart_start, chart.chart_end);
    const tracked = rows.some((row) => row.percentBp !== undefined && row.percentBp !== null);
    return buildGanttSvg({
      title,
      caption: `Contract months from ${chart.chart_start} · through ${chart.chart_end} · as of ${chart.as_of}`,
      columns,
      tracked,
      asOfPct: dateOffsetPct(chart.as_of, columns),
      rows: rows.map((row) => ({ ...row, ...barSpan(row.startDate, row.dueDate, columns) })),
    });
  }, [chart, rows, title]);

  if (!image) {
    return <p className="muted">{empty}</p>;
  }

  const dataUrl = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(image.svg)}`;
  const fileName = `${(title || "gantt").toLowerCase().replace(/[^a-z0-9]+/g, "-")}.png`;

  async function copyImage() {
    setNotice("");
    try {
      const blob = await rasterize(image, dataUrl);
      await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
      setNotice("Chart copied. Paste it into Word, PowerPoint, or email.");
    } catch {
      setNotice("This browser blocked the clipboard. Use Download PNG instead.");
    }
  }

  async function downloadPng() {
    setNotice("");
    try {
      const blob = await rasterize(image, dataUrl);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = fileName;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setNotice(err.message);
    }
  }

  return (
    <div className="month-gantt">
      <img
        className="mg-image"
        src={dataUrl}
        width={image.width}
        height={image.height}
        alt={`${title || "Gantt"}: ${rows.length} rows from ${chart.chart_start} to ${chart.chart_end}`}
      />
      <div className="mg-actions">
        <button type="button" className="secondary" onClick={copyImage}>
          Copy image
        </button>{" "}
        <button type="button" className="secondary" onClick={downloadPng}>
          Download PNG
        </button>{" "}
        <span className="muted">Right-click the chart to copy or save it as well.</span>
      </div>
      {notice ? <p className="muted">{notice}</p> : null}
    </div>
  );
}
