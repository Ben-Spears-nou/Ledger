// Month-column geometry for the contract and work Gantts.
//
// Columns are contract months counted from the chart start (M1 begins on the
// period-of-performance start date), not calendar months. An award starting on
// 31 August therefore puts kickoff work in M1 instead of leaving M1 empty.
// Every column is one calendar month long and all columns are drawn the same
// width, so bars stay comparable across the chart.
const DAY_MS = 86400000;
const MAX_COLUMNS = 600;

function parseIso(iso) {
  const [year, month, day] = iso.split("-").map(Number);
  return { year, month: month - 1, day };
}

function daysInMonth(year, month) {
  return new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
}

function toDayNumber({ year, month, day }) {
  return Math.round(Date.UTC(year, month, day) / DAY_MS);
}

function isoFromDayNumber(dayNumber) {
  return new Date(dayNumber * DAY_MS).toISOString().slice(0, 10);
}

// Calendar-month step from the anchor, clamped to the shortest month so a
// 31st-of-the-month start does not skip a month.
function addMonths(anchor, count) {
  const shifted = anchor.month + count;
  const year = anchor.year + Math.floor(shifted / 12);
  const month = ((shifted % 12) + 12) % 12;
  return { year, month, day: Math.min(anchor.day, daysInMonth(year, month)) };
}

export function monthColumns(startIso, endIso) {
  if (!startIso || !endIso) {
    return [];
  }
  const anchor = parseIso(startIso);
  const endDay = toDayNumber(parseIso(endIso));
  const columns = [];
  for (let index = 0; index < MAX_COLUMNS; index += 1) {
    const fromDay = toDayNumber(addMonths(anchor, index));
    const toDay = toDayNumber(addMonths(anchor, index + 1));
    columns.push({
      key: `m${index + 1}`,
      label: `M${index + 1}`,
      from: isoFromDayNumber(fromDay),
      to: isoFromDayNumber(toDay - 1),
      fromDay,
      toDay,
    });
    if (toDay > endDay) {
      break;
    }
  }
  return columns;
}

function offsetFromDay(dayNumber, columns) {
  if (!columns.length) {
    return 0;
  }
  const first = columns[0];
  const last = columns[columns.length - 1];
  if (dayNumber <= first.fromDay) {
    return 0;
  }
  if (dayNumber >= last.toDay) {
    return columns.length;
  }
  const index = columns.findIndex(
    (column) => dayNumber >= column.fromDay && dayNumber < column.toDay,
  );
  const column = columns[index];
  return index + (dayNumber - column.fromDay) / (column.toDay - column.fromDay);
}

export function dateOffsetPct(iso, columns) {
  if (!iso || !columns.length) {
    return null;
  }
  const dayNumber = toDayNumber(parseIso(iso));
  const last = columns[columns.length - 1];
  if (dayNumber < columns[0].fromDay || dayNumber >= last.toDay) {
    return null;
  }
  return (offsetFromDay(dayNumber, columns) / columns.length) * 100;
}

export function barSpan(startIso, dueIso, columns) {
  const total = columns.length;
  if (!total) {
    return { leftPct: 0, widthPct: 0 };
  }
  const from = offsetFromDay(toDayNumber(parseIso(startIso)), columns);
  // Due date is inclusive, so run the bar through the end of that day.
  const through = offsetFromDay(toDayNumber(parseIso(dueIso)) + 1, columns);
  const to = Math.min(Math.max(through, from), total);
  const leftPct = (from / total) * 100;
  const widthPct = Math.max(((to - from) / total) * 100, 0.35);
  return { leftPct, widthPct: Math.min(widthPct, 100 - leftPct) };
}
