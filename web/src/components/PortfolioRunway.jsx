import { Link } from "react-router-dom";
import { awardBarColors } from "../awardColors.js";

const PAD = 34;
const LABEL = 145;
const WIDTH = 860;
const ROW_HEIGHT = 34;
const INK = "#1b1f24";
const MUTED = "#6a655c";
const GRID = "#ddd8cb";
const DANGER = "#8a1f1f";

export default function PortfolioRunway({ rows }) {
  const usable = rows.filter((row) => row.days_to_pop_end >= 0);
  if (!usable.length) return <p className="muted">No active runway data.</p>;
  const maxDays = Math.max(
    ...usable.flatMap((row) => [row.days_to_pop_end || 0, row.runway_days || 0]),
    30,
  );
  const chartWidth = WIDTH - LABEL - PAD;
  const height = PAD * 2 + usable.length * ROW_HEIGHT;
  const x = (days) => LABEL + (Math.max(0, days) / maxDays) * chartWidth;

  return (
    <div className="portfolio-runway">
      <h2>Runway versus period of performance</h2>
      <p className="muted">
        Each project’s colored bar is financial runway; the marker is days remaining in the PoP.
        A red gap means the current burn rate reaches the approved limit first.
      </p>
      <div className="forecast-svg-scroll">
        <svg viewBox={`0 0 ${WIDTH} ${height}`} style={{ minWidth: WIDTH }} role="img">
          <title>Portfolio financial runway compared with days to period-of-performance end</title>
          {[0, 0.25, 0.5, 0.75, 1].map((part) => {
            const xx = LABEL + chartWidth * part;
            return (
              <g key={part}>
                <line x1={xx} x2={xx} y1={PAD - 8} y2={height - PAD} stroke={GRID} />
                <text x={xx} y={16} textAnchor="middle" fontSize="10" fill={MUTED}>
                  {Math.round(maxDays * part)}d
                </text>
              </g>
            );
          })}
          {usable.map((row, index) => {
            const yy = PAD + index * ROW_HEIGHT + ROW_HEIGHT / 2;
            const runway = row.runway_days;
            const popDays = row.days_to_pop_end;
            const shortCode = row.short_code || row.award_short_code;
            const color = awardBarColors(index).fill;
            const shortfall = runway !== null && runway < popDays;
            return (
              <g key={row.award_id}>
                <Link to={`/awards/${row.award_id}`}>
                  <text x={LABEL - 10} y={yy + 4} textAnchor="end" fontSize="11" fill={INK}>
                    {shortCode}
                  </text>
                </Link>
                {runway !== null ? (
                  <rect
                    x={LABEL}
                    y={yy - 7}
                    width={Math.max(2, x(runway) - LABEL)}
                    height="14"
                    rx="3"
                    fill={color}
                  >
                    <title>{`${shortCode}: ${runway} runway days`}</title>
                  </rect>
                ) : (
                  <text x={LABEL + 5} y={yy + 4} fontSize="10" fill={MUTED}>
                    no current burn
                  </text>
                )}
                {shortfall ? (
                  <line
                    x1={x(runway)}
                    x2={x(popDays)}
                    y1={yy}
                    y2={yy}
                    stroke={DANGER}
                    strokeWidth="4"
                    strokeDasharray="4 3"
                  />
                ) : null}
                <line
                  x1={x(popDays)}
                  x2={x(popDays)}
                  y1={yy - 11}
                  y2={yy + 11}
                  stroke={INK}
                  strokeWidth="2"
                >
                  <title>{`${shortCode}: ${popDays} days to PoP end (${row.pop_end})`}</title>
                </line>
                {shortfall ? (
                  <text x={x(popDays) + 5} y={yy + 4} fontSize="10" fill={DANGER}>
                    {popDays - runway}d short
                  </text>
                ) : null}
              </g>
            );
          })}
        </svg>
      </div>
      <div className="forecast-legend">
        <span>
          <i style={{ background: "#2f6f9f" }} />
          Colored runway
        </span>
        <span>
          <i className="legend-marker" />
          PoP end
        </span>
        <span>
          <i style={{ background: DANGER }} />
          Shortfall
        </span>
      </div>
    </div>
  );
}
