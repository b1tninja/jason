import { Embed } from "jason-ui";

// Offline-renderable stand-ins as blob URLs, so the cards verify without the network. In the app an image or PDF ref is
// a path under data/ (served by /api/file) or a URL, and a doc/sheet/form/drive ref is the Google file id.
const svg = "<svg xmlns='http://www.w3.org/2000/svg' width='480' height='300'><rect width='480' height='300' fill='#dde1e7'/><circle cx='240' cy='130' r='60' fill='#98a3b3'/><rect x='60' y='210' width='360' height='40' fill='#98a3b3'/><text x='240' y='285' text-anchor='middle' font-family='system-ui' font-size='14' fill='#5f6b7a'>east bed, before</text></svg>";
const photo = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
const page = URL.createObjectURL(new Blob([
  "<!doctype html><meta charset=utf-8><body style='margin:0;padding:1rem 1.25rem;font:15px/1.5 system-ui;color:#1c2330'><h2 style='margin:0 0 .5rem'>Notice of Hearing</h2><p>To the owner of unit 12: the board will hear the matter of the unapproved patio enclosure on <b>October 20, 2026 at 6:30 PM</b>.</p><p style='color:#5f6b7a'>A filled letter, as a Google Doc's preview frame shows it.</p></body>",
], { type: "text/html" }));

/** A photo on the canvas, with its caption and an open link. */
export const Photo = () => <Embed a={{ kind: "image", ref: photo, title: "East bed, before (2026-09-01)" }} />;

/** A document in a frame with its caption: how a Google Doc, Sheet, Form, Drive file, or PDF sits on the canvas. */
export const Document = () => <Embed a={{ kind: "url", ref: page, title: "Notice of Hearing, unit 12 (filled copy)" }} height={220} />;
