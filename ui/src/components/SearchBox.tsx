export function SearchBox({ value, onChange, label = "Filter" }: { value: string; onChange: (v: string) => void; label?: string }) {
  return (
    <input
      type="search"
      className="search"
      aria-label={label}
      placeholder={`${label}…`}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
