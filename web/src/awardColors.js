// One hue per award so portfolio Gantts separate projects at a glance.
// Single-award charts keep the lane colors from ganttSvg.
const HUES = [212, 148, 280, 28, 330, 192, 96, 256, 8, 62];

export function awardBarColors(index) {
  const hue = HUES[((index % HUES.length) + HUES.length) % HUES.length];
  return {
    planned: `hsl(${hue} 32% 84%)`,
    fill: `hsl(${hue} 56% 40%)`,
  };
}
