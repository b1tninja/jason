# Insurance policies, term by term

`jason policies` reads each insurance policy from its own papers. It sets them beside the board's policy sheet and the specification, and writes one page per policy. The pages and the papers are the AnythingLLM `insurance` catalog, so a question about coverage is answered from the policies themselves.

## Where each fact comes from

| Source | What it gives |
|---|---|
| The specification (`mystique/insurance.py`) | kind, carrier, program, agent, the number in force and earlier numbers, the end of the term in force, the master deductible |
| The policy sheet ("Vendors, Utilities, Accounts, Taxes, and Insurance", tab Insurance; read-only) | number, renewal date, premium by year, and the linked policy file |
| Drive (read-only) | every file that prints one of a policy's numbers (the full-text search), plus the files the sheet links |
| The library and email | the policy papers that arrived there, such as the D&O binder, which came only by email |

`--fetch` copies each policy's own papers into `data/insurance/documents`, one copy per content. These are the declarations and policy forms, binders and evidence, certificates, renewal and cancellation notices, premium invoices, and the annual disclosure. A lawsuit's demand, a lender's questionnaire, a resale packet, the books, and minutes that print a number are left where they are. A claim's papers stay in the incident history ([incidents.md](incidents.md)).

## The readers

The readers are in `jason.community.models.contracts_ins_package` and `contracts_insurance`, and they sort ahead of the general declarations reader (`register(..., first=True)`). They find the declarations inside a carrier's packet.

| Model | Reads |
|---|---|
| `package-declarations` | Accelerant's "POLICY DECLARATIONS - Condominium Assoc." through Arden (the master policy): number and renewed number, period, premium by coverage part, the named insured's mailing address, premises, building limit, valuation, deductible, business income, equipment breakdown, protective safeguards, liability limits, units, and the schedule of forms (the terrorism exclusion, the unit-interior form) |
| `crime-declarations` | PMA's Commercial Crime Policy Declarations: period, premium, and each insuring agreement's limit and deductible. The limits print in a run after the agreements and are read in the form's order |
| `dno-declarations` | MG Skinner's D&O/Crime binder with Accredited Surety and Casualty's declarations: number, period, aggregate limit, retention, premium, prior litigation date, claims-made, mailing address |
| `umbrella-evidence` | McGowan's umbrella Evidence of Insurance (Federal Insurance): evidence number, period, limits, retained limit, premium |
| `nfip-flood-declarations`, `acord-certificate` | the NFIP flood declarations and the ACORD certificates (already in `contracts_insurance`) |

**Checks:**

- **Civil Code 5800(a)(4):** general liability and D&O of at least $500,000 for volunteer directors' immunity.
- **Civil Code 5805(b):** $2,000,000 of general liability for owners' protection, counting the umbrella.
- **Civil Code 5806:** crime coverage of at least reserves plus three months' assessments, including computer and funds-transfer fraud. Reserves come from the stored ledger; the monthly assessment comes from the latest annual disclosure, times the units.
- **Civil Code 5810:** a mailing address that is not the association's, since the carrier's notices go there.
- **Protective safeguards:** a condition the property coverage depends on.
- **Specification:** a declarations number or deductible that differs from it.

The report adds:

- the sheet carrying an earlier term's number, a renewal date nothing supports, or a missing premium;
- a renewed term whose declarations are not on file;
- the next term's declarations already issued.

## Use

Copy each command on its own:

```bash
jason policies --fetch
```

```bash
jason policies --policy fidelity
```

```bash
jason anythingllm --sync --catalog insurance
```

```bash
jason anythingllm --ask "What is the master policy's deductible and does it cover unit interiors?" --catalog insurance
```

The `insurance_policies` board tool reads the stored report (`data/reports/policies.json`); `policy` narrows it to one policy. The pages are `data/insurance/pages/<policy>.md`, with `overview.md` covering every policy. Nothing is sent, moved, or changed in Drive, the sheet, or PayHOA.

Mystique's findings are in the private notes (mystique/notes/insurance-policies.md).

## Limits

- **What the report reads.** It reads what the papers print. An endorsement issued mid-term, or a policy never saved to Drive, email, or the library, is not here.
- **The crime limits.** They are read in the printed order of the insuring agreements; the carrier's declarations govern.
- **Reserves.** The reserve figure is the stored ledger's latest balance on the reserve accounts. The statement is the record.
