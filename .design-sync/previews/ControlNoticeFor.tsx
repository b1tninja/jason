import { ControlNoticeFor } from "jason-ui";

// ControlNoticeFor reads `GET /api/control-notices?subject=<kind>[&amount=N]`. A module-scope fetch stub answers by subject (made-up
// Oakview data, fake 2099 dates), so every cell on the card can share it. Any other subject answers 403, and the line then shows nothing.
const base: any = {
  found: true, subject: "", subjectKind: "approval kind", title: "Payment plans", builtin: "one person", why: "",
  stricter: false, second: { always: false, aboveCents: null }, roles: [], mustInclude: [], clash: "", asOf: "2099-10-12",
  controls: [], waiting: [], refusals: [], caveats: [],
};
const signers = { key: "payment-signers", title: "Payment signers", adoptedOn: "2099-09-05T20:00:00+00:00", effective: "2099-09-20", effect: "signers: 2", link: "#/controls?key=payment-signers" };
const delivery = {
  key: "delivery-class", title: "Delivery class", adoptedOn: "2099-10-03T20:00:00+00:00", effective: "2099-11-14", effect: "first class",
  link: "#/controls?key=delivery-class", reason: "adopted, not in force until 2099-11-14",
};
const BY_SUBJECT: Record<string, any> = {
  "sample-payments": { ...base, subject: "sample-payments", stricter: true, why: "Two signers are required above $2,500.00.", controls: [signers] },
  "sample-letters": { ...base, subject: "sample-letters", subjectKind: "send", title: "Notice letters", builtin: "standard mail", waiting: [delivery] },
  "sample-clash": {
    ...base, subject: "sample-clash", title: "Payment plans", controls: [signers], stricter: true,
    clash: "Two controls name different signers for this kind; the stricter applies until the board settles it.",
  },
  "sample-reviews": {
    ...base, subject: "sample-reviews", subjectKind: "workflow step", title: "Monthly review", controls: [signers],
    refusals: ["Monthly review requires a treasurer and a vice president; the roster has no vice president"],
  },
};
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const realFetch = globalThis.fetch;
globalThis.fetch = (async (input: any, init?: any) => {
  const url = String(typeof input === "string" ? input : input?.url ?? input);
  if (url.startsWith("/api/control-notices")) {
    const subject = new URL(url, "http://localhost").searchParams.get("subject") ?? "";
    return BY_SUBJECT[subject] ? json(200, BY_SUBJECT[subject]) : json(403, { error: "not for this viewer" });
  }
  return realFetch ? realFetch(input, init) : json(404, { error: "not here" });
}) as typeof fetch;

const Frame = ({ children }: { children: React.ReactNode }) => <div style={{ maxWidth: 720 }}>{children}</div>;

/** The line at an approval kind: what the control the board adopted requires here, read from the loader. */
export const AtAnApprovalKind = () => <Frame><ControlNoticeFor subject="sample-payments" amountCents={300000} /></Frame>;

/** At a send: a control adopted whose date has not come, in the muted form. */
export const AtASendNotYetRequired = () => <Frame><ControlNoticeFor subject="sample-letters" /></Frame>;

/** At a workflow step: a control in force and the server's refusal when the roster cannot satisfy it. */
export const AtAStepRefused = () => <Frame><ControlNoticeFor subject="sample-reviews" /></Frame>;

/** Two controls that disagree: the loader's own clash sentence follows the required line, so the page invents none. */
export const WithAClash = () => <Frame><ControlNoticeFor subject="sample-clash" /></Frame>;
