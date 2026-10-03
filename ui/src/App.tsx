import { useState } from "react";
import { AppShell, Card, ErrorNotice, Loading, Tabs } from "./components";
import { DigestView, type Digest } from "./DigestView";
import { useApi } from "./lib/useApi";

function BoardDigest() {
  const r = useApi<Digest>("/api/board-digest");
  if (r.status === "loading") return <Loading />;
  if (r.status === "error") return <ErrorNotice error={r.error} onRetry={r.reload} />;
  return <DigestView digest={r.data} />;
}

function Status() {
  const r = useApi<{ ok: boolean; ui: boolean; sources: string[] }>("/api/health");
  if (r.status === "loading") return <Loading />;
  if (r.status === "error") return <ErrorNotice error={r.error} onRetry={r.reload} />;
  return (
    <Card title="Server">
      <p>Sources: {r.data.sources.join(", ") || "none"}</p>
    </Card>
  );
}

export function App() {
  const [tab, setTab] = useState("digest");
  return (
    <AppShell title="Jason">
      <Tabs
        active={tab}
        onChange={setTab}
        tabs={[
          { id: "digest", label: "Board digest", content: <BoardDigest /> },
          { id: "status", label: "Status", content: <Status /> },
        ]}
      />
    </AppShell>
  );
}
