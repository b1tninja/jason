import { Badge } from "./Badge";
import { toneOf } from "../lib/tones";

/** A status or standing word with its tone, and its meaning on hover when the record carries one. */
export function Pill({ word, meaning }: { word: string | null | undefined; meaning?: string }) {
  if (!word) return null;
  const text = String(word).replace(/_/g, " ").toLowerCase();
  return (
    <span title={meaning}>
      <Badge tone={toneOf(text)}>{text}</Badge>
    </span>
  );
}
