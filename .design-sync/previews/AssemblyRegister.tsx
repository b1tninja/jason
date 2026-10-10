import { AssemblyRegister, inspectionFixtures as fx } from "jason-ui";

const docProps = { signedIn: true, evidence: null } as const;

/** Three devices, a column per source, history behind a disclosure. */
export const Devices = () => <AssemblyRegister assemblies={fx.assemblies} docProps={docProps} />;

/** A count that differs between sources shows a discrepancy row above the devices. */
export const WithDiscrepancy = () => <AssemblyRegister assemblies={fx.assemblies} discrepancies={[fx.discrepancy]} docProps={docProps} />;

/** A failed device with its repair clock, and a device no source has. */
export const FailedAndUnlisted = () => <AssemblyRegister assemblies={[fx.assemblies[1], { ...fx.assemblies[2], ids: [] }]} repairClocks={{ "SN-0002": fx.deadline }} docProps={docProps} />;

/** None on record. */
export const Empty = () => <AssemblyRegister assemblies={[]} />;
