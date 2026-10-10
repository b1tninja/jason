import { Card } from "./Card";
import { Command } from "./Command";
import { Confirm } from "./Confirm";
import { Pill } from "./Pill";
import { PortalReportRow } from "./PortalReportRow";
import type { ReportPortal } from "../lib/inspections";

/** A vendor's public report portal, from the loader's payload. It renders the loader's counts and never works out
 * "missing" itself. States:
 * - `portal` null: not found yet; names the command that finds it (`findCommand`). `vendorHasNone`: the vendor row says
 *   it has no portal, said as a fact about the row.
 * - found, not synced (`fetched` empty): says so and shows the sync command.
 * - synced: the counts, the last read, and each report (`PortalReportRow`).
 * - protected: a stop with a person's step. The portal asks for a password or a phone code, and jason enters neither.
 * - unreachable (a `note` and no reports): the error and the command.
 * - the same customer as another portal: listed once, pointing at the other.
 * The sync is a job a person starts: its `Command`, and with `onSync` a `Confirm` where it writes the portal's list to
 * jason's store. `onPlanFiling` opens the filing plan. */
export function ReportPortalCard({ portal, vendor, findCommand, syncCommand, vendorHasNone = false, onSync, onPlanFiling }: {
  portal: ReportPortal | null;
  vendor?: string;
  findCommand?: string;
  syncCommand?: string;
  vendorHasNone?: boolean;
  onSync?: (portal: ReportPortal) => void;
  onPlanFiling?: (portal: ReportPortal) => void;
}) {
  if (!portal) {
    return (
      <Card title={`Report portal: ${vendor ?? "vendor"}`}>
        {vendorHasNone
          ? <p><Pill word="none" meaning="The vendor's row records that it has no report portal." glyph="info" /> The vendor's row says it has no report portal. Nothing is searched for.</p>
          : <>
              <p><Pill word="not found" meaning="No document's code has named a portal for this vendor yet. A lead, not a finding that none exists." glyph="circle-dashed" /> No portal found yet. A portal is found from a QR code on one of the vendor's reports.</p>
              {findCommand && <Command cmd={findCommand} />}
            </>}
      </Card>
    );
  }
  const synced = !!portal.fetched;
  const unreachable = !!portal.note && !portal.protected && !portal.reports.length;
  const state = portal.protected ? "protected" : unreachable ? "unreachable" : synced ? "synced" : "found, not synced";
  const c = portal.counts;
  return (
    <Card title={`Report portal: ${portal.vendor}`} actions={<Pill word={state} glyph={portal.protected ? "lock" : unreachable ? "octagon-alert" : synced ? "circle-check" : "circle-dashed"}
      meaning={portal.protected ? "A person's step: the portal asks for a password or a phone code." : unreachable ? "The portal could not be read." : synced ? "jason has read the portal's list." : "A document's code named it; its list has not been read."} />}>
      <p className="muted">Customer: {portal.customer} · portal <code className="chip">{portal.key}</code></p>
      {portal.readFrom.length > 0 && <p className="muted">Named by the code on: {portal.readFrom.join(", ")}.</p>}
      {portal.sameCustomerAs && <p role="note">The same customer as portal <code className="chip">{portal.sameCustomerAs}</code>, which lists it. This one is listed once.</p>}

      {portal.protected && (
        <div className="notice notice-warn insp-stop" role="note">
          <p><strong>A person's step.</strong> This portal asks for a password or a phone code. jason enters neither.</p>
          <p>A person signs in at the portal and brings the reports back.</p>
        </div>
      )}

      {unreachable && (
        <>
          <div role="alert" className="notice notice-error"><span>{portal.note}</span></div>
          {syncCommand && <Command cmd={syncCommand} />}
        </>
      )}

      {!portal.protected && !unreachable && !synced && (
        <>
          <p>Found from a document's code and not read yet. jason has not opened the portal.</p>
          {syncCommand && <Command cmd={syncCommand} />}
          {onSync && <Confirm summary="Read the portal's list of reports and keep it in jason's store. Nothing is entered on the portal, and nothing is filed in Drive." onConfirm={() => onSync(portal)} label="Sync">Read the portal's list</Confirm>}
        </>
      )}

      {synced && !portal.protected && (
        <>
          <dl className="insp-counts" aria-label="Counts from the loader">
            <div><dt>Listed</dt><dd className="num">{c.listed}</dd></div>
            <div><dt>On disk</dt><dd className="num">{c.onDisk}</dd></div>
            <div><dt>In the library</dt><dd className="num">{c.inLibrary}</dd></div>
            <div><dt>Not filed</dt><dd className="num">{c.notFiled}</dd></div>
          </dl>
          <p className="muted">Last read <time dateTime={portal.fetched}>{portal.fetched}</time>. These counts are the loader's.</p>
          {portal.note && <p role="note" className="notice notice-warn">{portal.note}</p>}
          <div className="stack insp-reports">{portal.reports.map((r) => <PortalReportRow key={r.urlUuid} report={r} />)}</div>
          <div className="row wrap">
            {onPlanFiling && <button onClick={() => onPlanFiling(portal)}>Plan the filing</button>}
            {syncCommand && <Command cmd={syncCommand} note="Reads the portal's list again. Nothing is filed." />}
          </div>
        </>
      )}
    </Card>
  );
}
