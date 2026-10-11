import { Glyph } from "./Glyph";
import { controlHref, dayOf, noticesUrl, useControlsApi, type ControlNotices, type NoticeControl } from "../lib/controls";

const adopted = (n: NoticeControl) => (dayOf(n.adoptedOn) ? ` on ${dayOf(n.adoptedOn)}` : "");
const sentence = (s: string) => (s && !/[.!?]$/.test(s) ? `${s}.` : s);
const href = (n: NoticeControl) => n.link || controlHref(n.key);

/** The one line at the point of an act: what a control the board adopted requires here, with the control's title as a link
 * to its card. `data` is `GET /api/control-notices?subject=` (an approval kind, a workflow step, or a send). Read only; it
 * never hides a control and never narrows what a board member may read. It names only a control in force (the loader
 * leaves out a suggestion, a proposal, a declined, deferred, or retired control), and shows an adopted control whose date
 * has not come in the muted form: "Takes effect DATE; not yet required". The server refuses the act whatever this line
 * says; a refusal is shown in the server's words. Renders nothing when no control touches the subject. */
export function ControlNotice({ data }: { data: ControlNotices | null | undefined }) {
  if (!data || data.found === false) return null;
  const { controls, waiting, refusals } = data;
  if (!controls.length && !waiting.length && !refusals.length) return null;
  return (
    <aside className="control-notice" aria-label="Required by a control" data-subject={data.subject}>
      {controls.map((n, i) => (
        <p key={n.key} className="control-notice-line">
          <Glyph name="shield-check" size="1em" />{" "}
          <strong>Required by a control the board adopted{adopted(n)}:</strong> <a href={href(n)}>{n.title}</a>.
          {i === 0 && data.why ? <> {data.why}</> : null}
          {n.effect ? <span className="muted"> {n.effect}</span> : null}
        </p>
      ))}
      {data.stricter && data.builtin && <p className="muted control-notice-line">The kind's own rule is {data.builtin}.</p>}
      {data.clash && <p className="control-notice-line">{data.clash}</p>}
      {waiting.map((n) => (
        <p key={n.key} className="muted control-notice-line control-notice-waiting">
          <Glyph name="calendar-clock" size="1em" />{" "}
          {n.effective ? `Takes effect ${n.effective}; not yet required` : "Not yet required"}:{" "}
          <a href={href(n)}>{n.title}</a>, a control the board adopted{adopted(n)}.{n.reason ? <> {sentence(n.reason)}</> : null}
        </p>
      ))}
      {refusals.map((r) => (
        <p key={r} className="control-notice-line control-notice-refused" role="note">
          <Glyph name="ban" size="1em" /> <strong>Refused:</strong> {sentence(r)} A control never falls back to fewer.
        </p>
      ))}
    </aside>
  );
}

/** The notice for one subject, read from the loader (`subject` is a kind's key, a step, or a send; `amountCents` lets a plan
 * ask what its total adds). A subject that cannot be read, or a viewer the loader refuses, shows nothing: the line is an
 * aid, never the gate. */
export function ControlNoticeFor({ subject, amountCents }: { subject: string; amountCents?: number }) {
  const r = useControlsApi<ControlNotices>(noticesUrl(subject, amountCents));
  return <ControlNotice data={r.status === "ready" ? r.data : null} />;
}
