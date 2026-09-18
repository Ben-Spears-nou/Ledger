export default function CollapsibleSection({ title, className = "", children, ...props }) {
  const classes = ["card", "collapsible-section", className].filter(Boolean).join(" ");

  return (
    <details className={classes} {...props}>
      <summary>
        <span>{title}</span>
      </summary>
      <div className="collapsible-section-body">{children}</div>
    </details>
  );
}
