export default function CollapsibleSection({
  title,
  className = "",
  children,
  open,
  onOpenChange,
  ...props
}) {
  const classes = ["card", "collapsible-section", className].filter(Boolean).join(" ");
  const controlled = open !== undefined;

  return (
    <details
      className={classes}
      {...(controlled ? { open } : {})}
      onToggle={onOpenChange ? (event) => onOpenChange(event.currentTarget.open) : undefined}
      {...props}
    >
      <summary>
        <span>{title}</span>
      </summary>
      <div className="collapsible-section-body">{children}</div>
    </details>
  );
}
