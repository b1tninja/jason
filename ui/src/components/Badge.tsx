export type Tone = "neutral" | "good" | "warn" | "bad";

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: string }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}
