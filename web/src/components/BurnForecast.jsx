import { formatCents } from "../api.js";
import {
  expenseCategories,
  expenseColor,
  expenseLabel,
} from "../expenseColors.js";

const INK = "#1b1f24";
const MUTED = "#6a655c";
const GRID = "#ddd8cb";
const DEFAULT_PROJECT = "#2f6f9f";
const APPROVED = "#7a746a";
const FUNDED = "#aaa294";

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

function Legend({ items }) {
  return (
    <div className="forecast-legend">
      {items.map(([label, color, dashed]) => (
        <span key={label}>
          <i style={{ background: color, borderStyle: dashed ? "dashed" : "solid" }} />
          {label}
        </span>
      ))}
    </div>
  );
}

function NoData({ children = "No forecast data yet." }) {
  return <p className="muted">{children}</p>;
}

export function CumulativeForecastChart({ burn, color = DEFAULT_PROJECT }) {
  const rows = burn?.forecast_months || [];
  if (!rows.length) return <NoData />;
  const width = Math.max(720, rows.length * 54);
  const height = 270;
  const left = 66;
  const right = 16;
  const top = 18;
  const bottom = 42;
  const innerW = width - left - right;
  const innerH = height - top - bottom;
  const ceiling = Math.max(
    burn.approved_ceiling_cents || 0,
    burn.funded_ceiling_cents || 0,
    burn.eac_cents || 0,
    ...rows.map((row) =>
      Math.max(row.cumulative_actual_cents || 0, row.projected_cumulative_cents || 0),
    ),
    1,
  );
  const x = (index) => left + (rows.length === 1 ? innerW / 2 : (index * innerW) / (rows.length - 1));
  const y = (value) => top + innerH - (Math.max(0, value) / ceiling) * innerH;
  const asOfMonth = burn.as_of.slice(0, 7);
  const actualRows = rows.filter((row) => row.year_month <= asOfMonth);
  const futureStart = Math.max(0, rows.findIndex((row) => row.year_month >= asOfMonth));
  const path = (points, field, offset = 0) =>
    points
      .map((row, index) => `${index ? "L" : "M"} ${x(index + offset)} ${y(row[field])}`)
      .join(" ");
  const future = rows.slice(futureStart);
  const projectedPath =
    future.length > 1
      ? [
          `M ${x(futureStart)} ${y(burn.actual_cents)}`,
          ...future
            .slice(1)
            .map(
              (row, index) =>
                `L ${x(index + futureStart + 1)} ${y(row.projected_cumulative_cents)}`,
            ),
        ].join(" ")
      : "";

  return (
    <div className="forecast-chart">
      <h3>Cumulative burn and runway</h3>
      <p className="muted">
        Posted actuals with the selected burn-rate projection through the period of performance.
      </p>
      <div className="forecast-svg-scroll">
        <svg viewBox={`0 0 ${width} ${height}`} style={{ minWidth: width }} role="img">
          <title>Cumulative actual and projected costs against approved and funded ceilings</title>
          {[0, 0.25, 0.5, 0.75, 1].map((part) => {
            const yy = top + innerH * (1 - part);
            return (
              <g key={part}>
                <line x1={left} x2={width - right} y1={yy} y2={yy} stroke={GRID} />
                <text x={left - 8} y={yy + 4} textAnchor="end" fontSize="10" fill={MUTED}>
                  {compactMoney(ceiling * part)}
                </text>
              </g>
            );
          })}
          <line
            x1={left}
            x2={width - right}
            y1={y(burn.approved_ceiling_cents)}
            y2={y(burn.approved_ceiling_cents)}
            stroke={APPROVED}
            strokeWidth="2"
          />
          <line
            x1={left}
            x2={width - right}
            y1={y(burn.funded_ceiling_cents)}
            y2={y(burn.funded_ceiling_cents)}
            stroke={FUNDED}
            strokeWidth="2"
            strokeDasharray="5 4"
          />
          <path
            d={path(actualRows, "cumulative_actual_cents")}
            fill="none"
            stroke={color}
            strokeWidth="3"
          />
          {projectedPath ? (
            <path
              d={projectedPath}
              fill="none"
              stroke={color}
              strokeWidth="3"
              strokeDasharray="7 5"
            />
          ) : null}
          {rows.map((row, index) =>
            index % Math.max(1, Math.ceil(rows.length / 12)) === 0 ? (
              <text
                key={row.year_month}
                x={x(index)}
                y={height - 17}
                textAnchor="middle"
                fontSize="10"
                fill={MUTED}
              >
                {monthLabel(row.year_month)}
              </text>
            ) : null,
          )}
        </svg>
      </div>
      <Legend
        items={[
          ["Actual", color],
          [`Projected (${burn.selected_window_days}d rate)`, color, true],
          ["Approved ceiling", APPROVED],
          ["Funded ceiling", FUNDED, true],
        ]}
      />
    </div>
  );
}

function BarChart({ title, description, rows, series, lineValue, lineLabel, color }) {
  if (!rows.length) return <NoData />;
  const width = Math.max(720, rows.length * 58);
  const height = 260;
  const left = 62;
  const right = 14;
  const top = 16;
  const bottom = 44;
  const innerW = width - left - right;
  const innerH = height - top - bottom;
  const max = Math.max(
    lineValue || 0,
    ...rows.flatMap((row) => series.map((item) => row[item.key] || 0)),
    1,
  );
  const groupW = innerW / rows.length;
  const barW = Math.min(18, (groupW - 8) / series.length);
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
          {rows.map((row, index) => {
            const center = left + groupW * index + groupW / 2;
            return (
              <g key={row.year_month}>
                {series.map((item, seriesIndex) => {
                  const value = row[item.key];
                  if (value === null || value === undefined) return null;
                  const xx = center + (seriesIndex - (series.length - 1) / 2) * barW;
                  return (
                    <rect
                      key={item.key}
                      x={xx - barW / 2}
                      y={y(value)}
                      width={barW - 2}
                      height={Math.max(1, top + innerH - y(value))}
                      fill={item.color}
                      fillOpacity={item.opacity ?? 1}
                      rx="2"
                    >
                      <title>{`${monthLabel(row.year_month)} · ${item.label}: ${formatCents(value)}`}</title>
                    </rect>
                  );
                })}
                <text x={center} y={height - 17} textAnchor="middle" fontSize="10" fill={MUTED}>
                  {monthLabel(row.year_month)}
                </text>
              </g>
            );
          })}
          {lineValue ? (
            <line
              x1={left}
              x2={width - right}
              y1={y(lineValue)}
              y2={y(lineValue)}
              stroke={color || DEFAULT_PROJECT}
              strokeWidth="2"
              strokeDasharray="6 4"
            >
              <title>{`${lineLabel}: ${formatCents(lineValue)}`}</title>
            </line>
          ) : null}
        </svg>
      </div>
      <Legend
        items={[
          ...series.map((item) => [item.label, item.color]),
          ...(lineValue ? [[lineLabel, color || DEFAULT_PROJECT, true]] : []),
        ]}
      />
    </div>
  );
}

function CategoryBarChart({
  title,
  description,
  rows,
  measures,
  lineValue,
  lineLabel,
}) {
  if (!rows.length) return <NoData />;
  const categories = [
    ...new Set(measures.flatMap((measure) => expenseCategories(rows, measure.key))),
  ];
  const width = Math.max(720, rows.length * 62);
  const height = 275;
  const left = 64;
  const right = 14;
  const top = 18;
  const bottom = 45;
  const innerW = width - left - right;
  const innerH = height - top - bottom;
  const totals = rows.flatMap((row) =>
    measures.map((measure) =>
      Object.values(row[measure.key] || {}).reduce((sum, value) => sum + value, 0),
    ),
  );
  const max = Math.max(lineValue || 0, ...totals, 1);
  const groupW = innerW / rows.length;
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
          {rows.map((row, rowIndex) => {
            const center = left + groupW * rowIndex + groupW / 2;
            return (
              <g key={row.year_month}>
                {measures.map((measure, measureIndex) => {
                  let stacked = 0;
                  const xx = center + (measureIndex - (measures.length - 1) / 2) * barW;
                  return categories.map((category) => {
                    const value = row[measure.key]?.[category] || 0;
                    if (!value) return null;
                    const base = stacked;
                    stacked += value;
                    return (
                      <rect
                        key={category}
                        x={xx - barW / 2}
                        y={y(stacked)}
                        width={barW - 2}
                        height={Math.max(1, y(base) - y(stacked))}
                        fill={expenseColor(category)}
                        fillOpacity={measure.opacity}
                      >
                        <title>{`${monthLabel(row.year_month)} · ${measure.label} · ${expenseLabel(category)}: ${formatCents(value)}`}</title>
                      </rect>
                    );
                  });
                })}
                <text x={center} y={height - 17} textAnchor="middle" fontSize="10" fill={MUTED}>
                  {monthLabel(row.year_month)}
                </text>
              </g>
            );
          })}
          {lineValue ? (
            <line
              x1={left}
              x2={width - right}
              y1={y(lineValue)}
              y2={y(lineValue)}
              stroke={DEFAULT_PROJECT}
              strokeWidth="2"
              strokeDasharray="6 4"
            >
              <title>{`${lineLabel}: ${formatCents(lineValue)}`}</title>
            </line>
          ) : null}
        </svg>
      </div>
      <Legend items={categories.map((category) => [expenseLabel(category), expenseColor(category)])} />
      {measures.length > 1 ? (
        <p className="muted forecast-measures">
          {measures
            .map((measure) => `${measure.label}: ${Math.round(measure.opacity * 100)}% shade`)
            .join(" · ")}
        </p>
      ) : null}
    </div>
  );
}

export function MonthlyActualChart({ burn, color = DEFAULT_PROJECT }) {
  const rows = (burn?.forecast_months || []).filter((row) => row.year_month <= burn.as_of.slice(0, 7));
  return (
    <CategoryBarChart
      title="Monthly actual burn"
      description="Posted labor and expenses by category; the dashed line is the selected trailing daily rate × 30."
      rows={rows}
      measures={[{ key: "actual_by_category", label: "Actual", opacity: 1 }]}
      lineValue={burn.daily_burn_cents * 30}
      lineLabel={`${burn.selected_window_days}-day monthly rate`}
    />
  );
}

export function PlanActualChart({ burn, color = DEFAULT_PROJECT }) {
  return (
    <CategoryBarChart
      title="Planned labor, actuals, and commitments"
      description="Category colors separate labor and expenses. Assignment-based labor is a management plan."
      rows={burn?.forecast_months || []}
      measures={[
        { key: "actual_by_category", label: "Actual", opacity: 1 },
        { key: "planned_by_category", label: "Planned", opacity: 0.65 },
        { key: "commitment_by_category", label: "Commitments", opacity: 0.35 },
      ]}
    />
  );
}

export function FundingTimeline({ burn, color = DEFAULT_PROJECT }) {
  const rows = (burn?.forecast_months || []).filter((row) => row.funding_expected_cents > 0);
  return (
    <div className="forecast-chart">
      <h3>Expected funding inflows</h3>
      <p className="muted">
        Expected increments are timing markers only; they do not increase funded remaining until a
        modification is recorded.
      </p>
      {rows.length ? (
        <div className="funding-timeline">
          {rows.map((row) => (
            <div key={row.year_month} style={{ borderColor: color }}>
              <span>{monthLabel(row.year_month)}</span>
              <strong>{formatCents(row.funding_expected_cents)}</strong>
            </div>
          ))}
        </div>
      ) : (
        <NoData>No expected funding increments have been entered.</NoData>
      )}
    </div>
  );
}

export function BurnWindowComparison({ burn, onSelect, color = DEFAULT_PROJECT }) {
  const windows = burn?.windows || [];
  if (!windows.length) return <NoData />;
  const max = Math.max(...windows.map((row) => row.monthly_rate_cents), 1);
  return (
    <div className="forecast-chart">
      <h3>Burn-rate sensitivity</h3>
      <p className="muted">
        Select the trailing window used for EAC, runway, and the cumulative projection.
      </p>
      <div className="window-comparison">
        {windows.map((row) => (
          <button
            type="button"
            className={row.days === burn.selected_window_days ? "selected" : ""}
            key={row.days}
            onClick={() => onSelect(row.days)}
          >
            <span>{row.days} days</span>
            <strong>{formatCents(row.monthly_rate_cents)}/mo</strong>
            <i
              style={{
                width: `${(row.monthly_rate_cents / max) * 100}%`,
                background: color,
              }}
            />
          </button>
        ))}
      </div>
    </div>
  );
}

export default function BurnForecast({
  burn,
  asOf,
  onAsOfChange,
  onWindowSelect,
  color = DEFAULT_PROJECT,
  showDateControl = true,
}) {
  if (!burn) return null;
  return (
    <>
      <div className="forecast-toolbar">
        {showDateControl ? (
          <div>
            <label>Forecast as of</label>
            <input
              type="date"
              value={asOf}
              onChange={(event) => onAsOfChange(event.target.value)}
            />
          </div>
        ) : null}
        <div className="forecast-kpis">
          <div>
            <span>Daily burn</span>
            <strong>{formatCents(burn.daily_burn_cents)}</strong>
          </div>
          <div>
            <span>EAC at PoP end</span>
            <strong>{formatCents(burn.eac_cents)}</strong>
          </div>
          <div>
            <span>Runway</span>
            <strong>{burn.runway_days == null ? "n/a" : `${burn.runway_days} days`}</strong>
          </div>
          <div>
            <span>Runway end</span>
            <strong>{burn.runway_end || "n/a"}</strong>
          </div>
        </div>
      </div>
      <div className="forecast-grid">
        <CumulativeForecastChart burn={burn} color={color} />
        <MonthlyActualChart burn={burn} color={color} />
        <PlanActualChart burn={burn} color={color} />
        <FundingTimeline burn={burn} color={color} />
        <BurnWindowComparison burn={burn} onSelect={onWindowSelect} color={color} />
      </div>
    </>
  );
}
