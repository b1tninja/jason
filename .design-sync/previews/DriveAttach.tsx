import { useState } from "react";
import { DriveAttach, type DriveFile } from "jason-ui";

// The dialog searches /api/drive-files only once opened; these cells render closed, so nothing is fetched.

const packet: DriveFile[] = [
  { id: "f-bid-a", name: "Greenway Landscape bid 2027.pdf", kind: "pdf", url: "https://drive.google.com/file/d/f-bid-a/view" },
  { id: "f-bid-b", name: "Sierra Turf Care proposal.pdf", kind: "pdf", url: "https://drive.google.com/file/d/f-bid-b/view" },
  { id: "f-res", name: "Resolution 2026-14, landscape contract", kind: "doc", url: "https://docs.google.com/document/d/f-res" },
];

function Attach({ initial }: { initial: DriveFile[] }) {
  const [files, setFiles] = useState(initial);
  return <DriveAttach files={files} onChange={setFiles} />;
}

/** Three files attached: kind badge, name, Open for a real URL, Remove; the button and the catalog note under them. */
export const Attached = () => <Attach initial={packet} />;

/** Nothing attached yet: the button and the note only. */
export const Empty = () => <Attach initial={[]} />;

/** A file from the catalog without a link: no Open, Remove only; a long name is cut with an ellipsis. */
export const NoLink = () => (
  <Attach initial={[{ id: "f-ledger", name: "Reserve transfer ledger, 2026-07-15 through 2026-09-30, treasurer's copy with notes.xlsx", kind: "sheet", url: "" }]} />
);
