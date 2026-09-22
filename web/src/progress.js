// Percent-complete color ramp shared by the work-plan table and the work Gantt.
// Sand through amber to green; red stays reserved for behind-schedule lanes.
export function progressColor(bp) {
  const pct = Math.max(0, Math.min(100, bp / 100));
  const hue = 40 + (pct / 100) * 108;
  const saturation = 25 + (pct / 100) * 20;
  const lightness = 62 - (pct / 100) * 25;
  return `hsl(${hue} ${saturation}% ${lightness}%)`;
}
