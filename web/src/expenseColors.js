const CATEGORY_COLORS = {
  labor: "#1f7a4d",
  personnel: "#63a777",
  travel: "#2f6f9f",
  odc: "#d17a22",
  equipment: "#7d3fa1",
  sub: "#b54a4a",
  indirect: "#6f7378",
  fringe: "#4f9da6",
  fee: "#b28a18",
  other: "#8a8173",
};

const CATEGORY_LABELS = {
  labor: "Labor / hours",
  personnel: "Other personnel",
  travel: "Travel",
  odc: "ODC / materials",
  equipment: "Equipment",
  sub: "Subcontracts",
  indirect: "Indirect",
  fringe: "Fringe",
  fee: "Fee",
  other: "Other",
};

export function expenseColor(category) {
  return CATEGORY_COLORS[category] || CATEGORY_COLORS.other;
}

export function expenseLabel(category) {
  return CATEGORY_LABELS[category] || category;
}

export function expenseCategories(rows, field) {
  return [
    ...new Set(
      rows.flatMap((row) =>
        Object.entries(row[field] || {})
          .filter(([, cents]) => cents)
          .map(([category]) => category),
      ),
    ),
  ].sort((left, right) => expenseLabel(left).localeCompare(expenseLabel(right)));
}
