import { formatCents } from "../api.js";
import { awardBarColors } from "../awardColors.js";
import PortfolioRunway from "./PortfolioRunway.jsx";

const GRID = "#ddd8cb";
const MUTED = "#6a655c";

function compactMoney(cents) {
  const dollars = cents / 100;
  if (Math.abs(dollars) >= 1_000_000) return `$${(dollars / 1_000_000).toFixed(1)}m`;
  if (Math.abs(dollars) >= 1_000) return `$${(dollars / 1_000).toFixed(0)}k`;
  return `$${dollars.toFixed(0)}`;
}

function monthLabel(value) {
  const [year, month] = value.split("-").map(Number);
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    year: "2-digit",
    timeZone: "UTC",
  }).format(
    new Date(Date.UTC(year, month - 1, 1)),
  );
}

function monthsFor(burns) {
  return [...new Set(burns.flatMap((burn) => burn.forecast_months.map((row) => row.year_month)))].sort();
}

function monthRow(burn, month) {
  return burn.forecast_months.find((row) => row.year_month === month);
}

function AwardLegend({ burns }) {
  return (
    <div className="forecast-legend">
      {burns.map((burn, index) => (
        <span key={burn.award_id}>
          <i style={{ background: awardBarColors(index).fill }} />
          {burn.award_short_code}
        </span>
      ))}
    </div>
  );
}

function MultiCumulativeChart({ burns }) {
  const months = monthsFor(burns);
  if (!months.length) return null;
  const width = Math.max(720, months.length * 54);
  const height = 290;
  const left = 66;
  const right = 16;
  const top = 18;
  const bottom = 42;
  const innerW = width - left - right;
  const innerH = height - top - bottom;
  const max = Math.max(
    ...burns.flatMap((burn) => [
      burn.eac_cents || 0,
      burn.approved_ceiling_cents || 0,
      burn.funded_ceiling_cents || 0,
      ...burn.forecast_months.map((row) => row.projected_cumulative_cents || 0),
    ]),
    1,
  );
  const x = (month) =>
    left + (months.length === 1 ? innerW / 2 : (months.indexOf(month) * innerW) / (months.length - 1));
  const y = (value) => top + innerH - (Math.max(0, value) / max) * innerH;
  const line = (points, field) =>
    points.map((row, index) => `${index ? "L" : "M"} ${x(row.year_month)} ${y(row[field])}`).join(" ");

  return (
    <div className="forecast-chart">
      <h3>Cumulative burn and runway</h3>
      <p className="muted">Solid lines are posted actuals; dashed lines continue each award at the selected burn rate.</p>
      <div className="forecast-svg-scroll">
        <svg viewBox={`0 0 ${width} ${height}`} style={{ minWidth: width }} role="img">
          <title>Cumulative burn projection for all awards</title>
          {[0, 0.5, 1].map((part) => {
            const yy = top + innerH * (1 - part);
            return (
              <g key={part}>
                <line x1={left} x2={width - right} y1={yy} y2={yy} stroke={GRID} />
                <text x={left - 8} y={yy + 4} textAnchor="end" fontSize="10" fill={MUTED}>
                  {compactMoney(max * part)}
                </text>
              </g>
            );
          })}
          {burns.map((burn, index) => {
            const color = awardBarColors(index).fill;
            const actual = burn.forecast_months.filter(
              (row) => row.year_month <= burn.as_of.slice(0, 7),
            );
            const future = burn.forecast_months.filter(
              (row) => row.year_month >= burn.as_of.slice(0, 7),
            );
            const projection =
              future.length > 1
                ? `M ${x(future[0].year_month)} ${y(burn.actual_cents)} ${future
                    .slice(1)
                    .map(
                      (row) =>
                        `L ${x(row.year_month)} ${y(row.projected_cumulative_cents)}`,
                    )
                    .join(" ")}`
                : "";
            return (
              <g key={burn.award_id}>
                <path d={line(actual, "cumulative_actual_cents")} fill="none" stroke={color} strokeWidth="3" />
                {projection ? (
                  <path d={projection} fill="none" stroke={color} strokeWidth="3" strokeDasharray="7 5" />
                ) : null}
              </g>
            );
          })}
          {months.map((month, index) =>
            index % Math.max(1, Math.ceil(months.length / 12)) === 0 ? (
              <text key={month} x={x(month)} y={height - 17} textAnchor="middle" fontSize="10" fill={MUTED}>
                {monthLabel(month)}
              </text>
            ) : null,
          )}
        </svg>
      </div>
      <AwardLegend burns={burns} />
    </div>
  );
}

function StackedMonthlyChart({ burns, title, description, measures }) {
  const months = monthsFor(burns);
  if (!months.length) return null;
  const width = Math.max(720, months.length * 62);
  const height = 275;
  const left = 64;
  const right = 14;
  const top = 18;
  const bottom = 45;
  const innerW = width - left - right;
  const innerH = height - top - bottom;
  const totals = months.flatMap((month) =>
    measures.map((measure) =>
      burns.reduce((sum, burn) => sum + (monthRow(burn, month)?.[measure.key] || 0), 0),
    ),
  );
  const max = Math.max(...totals, 1);
  const groupW = innerW / months.length;
  const barW = Math.min(18, Math.max(5, (groupW - 8) / measures.length));
  const y = (value) => top + innerH - (Math.max(0, value) / max) * innerH;

  return (
    <div className="forecast-chart">
      <h3>{title}</h3>
      <p className="muted">{description}</p>
      <div className="forecast-svg-scroll">
        <svg viewBox={`0 0 ${width} ${height}`} style={{ minWidth: width }} role="img">
          <title>{title}</title>
          {[0, 0.5, 1].map((part) => {
            const yy = top + innerH * (1 - part);
            return (
              <g key={part}>
                <line x1={left} x2={width - right} y1={yy} y2={yy} stroke={GRID} />
                <text x={left - 7} y={yy + 4} textAnchor="end" fontSize="10" fill={MUTED}>
                  {compactMoney(max * part)}
                </text>
              </g>
            );
          })}
          {months.map((month, monthIndex) => {
            const center = left + groupW * monthIndex + groupW / 2;
            return (
              <g key={month}>
                {measures.map((measure, measureIndex) => {
                  let stacked = 0;
                  const xx = center + (measureIndex - (measures.length - 1) / 2) * barW;
                  return burns.map((burn, awardIndex) => {
                    const value = monthRow(burn, month)?.[measure.key] || 0;
                    if (!value) return null;
                    const base = stacked;
                    stacked += value;
                    return (
                      <rect
                        key={burn.award_id}
                        x={xx - barW / 2}
                        y={y(stacked)}
                        width={barW - 2}
                        height={Math.max(1, y(base) - y(stacked))}
                        fill={awardBarColors(awardIndex).fill}
                        fillOpacity={measure.opacity}
                      >
                        <title>{`${monthLabel(month)} · ${burn.award_short_code} · ${measure.label}: ${formatCents(value)}`}</title>
                      </rect>
                    );
                  });
                })}
                <text x={center} y={height - 17} textAnchor="middle" fontSize="10" fill={MUTED}>
                  {monthLabel(month)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <AwardLegend burns={burns} />
      {measures.length > 1 ? (
        <p className="muted forecast-measures">
          {measures.map((measure) => `${measure.label}: ${Math.round(measure.opacity * 100)}% shade`).join(" · ")}
        </p>
      ) : null}
    </div>
  );
}

function PortfolioFunding({ burns }) {
  const events = burns
    .flatMap((burn, index) =>
      burn.forecast_months
        .filter((row) => row.funding_expected_cents > 0)
        .map((row) => ({ ...row, burn, index })),
    )
    .sort((a, b) => a.year_month.localeCompare(b.year_month));
  return (
    <div className="forecast-chart">
      <h3>Expected funding inflows</h3>
      <p className="muted">Expected increments are timing markers and do not increase remaining until a modification is recorded.</p>
      {events.length ? (
        <div className="funding-timeline">
          {events.map((event) => (
            <div
              key={`${event.burn.award_id}-${event.year_month}`}
              style={{ borderColor: awardBarColors(event.index).fill }}
            >
              <span>{event.burn.award_short_code} · {monthLabel(event.year_month)}</span>
              <strong>{formatCents(event.funding_expected_cents)}</strong>
            </div>
          ))}
        </div>
      ) : (
        <p className="muted">No expected funding increments have been entered.</p>
      )}
    </div>
  );
}

function PortfolioWindows({ burns }) {
  const max = Math.max(
    ...burns.flatMap((burn) => burn.windows.map((row) => row.monthly_rate_cents)),
    1,
  );
  return (
    <div className="forecast-chart">
      <h3>Burn-rate sensitivity</h3>
      <p className="muted">Monthly equivalents from each award’s trailing 30, 60, and 90-day windows.</p>
      <div className="portfolio-windows">
        {burns.map((burn, index) => (
          <div key={burn.award_id}>
            <strong>{burn.award_short_code}</strong>
            {burn.windows.map((row) => (
              <div key={row.days}>
                <span>{row.days}d</span>
                <i style={{ width: `${(row.monthly_rate_cents / max) * 100}%`, background: awardBarColors(index).fill }} />
                <span>{formatCents(row.monthly_rate_cents)}/mo</span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function PortfolioForecast({ burns }) {
  if (!burns.length) return <p className="muted">No award forecast data.</p>;
  return (
    <div className="forecast-grid">
      <PortfolioRunway rows={burns} />
      <MultiCumulativeChart burns={burns} />
      <StackedMonthlyChart
        burns={burns}
        title="Monthly actual burn"
        description="Posted charges stacked by award."
        measures={[{ key: "actual_cents", label: "Actual", opacity: 1 }]}
      />
      <StackedMonthlyChart
        burns={burns}
        title="Planned labor, actuals, and commitments"
        description="Three monthly bars, each stacked by award color."
        measures={[
          { key: "actual_cents", label: "Actual", opacity: 1 },
          { key: "planned_cents", label: "Planned", opacity: 0.65 },
          { key: "commitment_cents", label: "Commitments", opacity: 0.35 },
        ]}
      />
      <PortfolioFunding burns={burns} />
      <PortfolioWindows burns={burns} />
    </div>
  );
}
