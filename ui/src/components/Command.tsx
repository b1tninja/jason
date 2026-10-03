import { useState } from "react";

/** The exact command a person would run in a terminal. The page shows and copies it; it never runs it. */
export function Command({ cmd, note = "Run it in a terminal. The page never runs a command." }: { cmd: string; note?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(cmd);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* no clipboard: the text is selectable */
    }
  };
  return (
    <div className="command">
      <pre><code>{cmd}</code></pre>
      <div className="row">
        <button onClick={copy} aria-label="Copy command">{copied ? "Copied" : "Copy"}</button>
        <span className="muted">{note}</span>
      </div>
    </div>
  );
}
