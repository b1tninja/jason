"""Vendor-format adapters: the general modules that read one vendor's own layout, declared as data.

A general reader never recognizes an association's counterparty by a name in its own pattern. It asks the profile's
sender directory (``sources.sender_in``), so another association's law firm, manager, or vendor is found the same way and
one the directory does not list is a miss.

An adapter is different. It reads the layout one vendor prints: a bank's statement, a carrier's declarations page, an
inspector's report, a vendor's invoice. The vendor's name in its pattern is that layout's own signature, the same for
every association the vendor serves, so it is not a fact about any one of them. Which adapters an association uses is
profile data (its senders, its policies, its accounts); that jason can read the layout is not.

The boundary check (``jason.community.boundary``) cannot tell the two apart from the code alone, so an adapter is
declared here. One ``Adapter`` row names the module, the vendor whose layout it reads, and what it reads. The check then
allows that vendor's name in that module's patterns, and nowhere else, and a general document may name the vendor in a
code span. A vendor's invoice layout is declared by its ``InvoiceFormat`` row (``invoice_formats.INVOICE_FORMATS``);
``adapters()`` takes those rows too. Every adapter is listed in ``docs/adapters.md`` (``python -m
jason.community.adapters`` prints the table), and a row whose module no longer names its vendor is stale and fails the
check: the list holds what the code reads, no more.

A public source is not declared here. The State, a county, a city, a federal program, a public utility district, and a
platform jason runs on are not an association's facts, and the boundary takes no terms from them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from jason.community.sources import fold


@dataclass(frozen=True)
class Adapter:
    """One vendor layout a general module reads.

    ``module`` is the module's path from the repository root. ``vendor`` is the vendor's name as the layout prints it.
    ``reads`` says what the layout is. ``signature`` holds other names the layout prints for the same vendor (a bank's
    full legal name, a trade name), which the module's patterns may carry as well.
    """

    module: str
    vendor: str
    reads: str
    signature: tuple[str, ...] = ()

    def names(self, term: str) -> bool:
        """Whether ``term`` is this vendor's name, or part of it, by whole words (letters and digits only)."""
        folded = fold(term)
        return bool(folded.strip()) and any(folded in fold(word) for word in (self.vendor, *self.signature))


_MODELS = "src/jason/community/models/"
INVOICE_MODULE = "src/jason/community/invoice_formats.py"

ADAPTERS: tuple[Adapter, ...] = (
    Adapter(_MODELS + "financial_bank.py", "JPMorgan Chase", "business checking and savings statements (`chase-statement`)",
            signature=("JPMorgan Chase Bank", "Chase.com")),
    Adapter(_MODELS + "contracts_ins_package.py", "Manufacturers Alliance Insurance Company",
            "commercial crime policy declarations in a carrier's packet (`crime-declarations`)"),
    Adapter(_MODELS + "contracts_ins_package.py", "Arden Insurance Services",
            "the master package policy's declarations in a program's packet (`package-declarations`)"),
    Adapter(_MODELS + "contracts_ins_package.py", "McGowan Program Administrators",
            "an umbrella's evidence of insurance and purchasing group membership (`umbrella-evidence`)"),
    Adapter(_MODELS + "invoices.py", "Philadelphia Indemnity Insurance Company",
            "NFIP flood renewal notice and new-application invoice (`flood-premium-notice`)"),
    Adapter(_MODELS + "elevated_elements.py", "California Deck Inspection",
            "exterior elevated elements inspection report (`sb326-report`)"),
    Adapter(_MODELS + "inspections_roof.py", "Good Life Inspections", "per-building roof inspection estimate (`roofchecks-roof-inspection`)",
            signature=("GoodLife Inspections", "North American Home Services")),
    Adapter(_MODELS + "contracts_agreements.py", "North American Home Services",
            "per-building roof estimate, as a contract and as a proposal (`nahs-roof-estimate`)"),
    Adapter(_MODELS + "legal_inspections.py", "Signal Service", "NFPA 72 fire alarm inspection report (`signal-service-fire-alarm`)"),
    Adapter(_MODELS + "meetings_elections.py", "Pro Elections",
            "an inspector of elections' results page, secret ballot, and pre-ballot notice (`election-results`)"),
    Adapter(_MODELS + "financial_annual.py", "CiraConnect", "a management platform's fund budget and resident budget package"),
    Adapter("src/jason/community/reserve_study.py", "California Builder Services", "reserve analysis report"),
    Adapter("src/jason/community/reserve_study.py", "The Helsing Group", "reserve funding update (the disclosure and its 30-year plan)"),
    Adapter("src/jason/community/reserve_study.py", "Browning Reserve Group", "reserve study (expenditures by year)"),
    Adapter("src/jason/signalservice/client.py", "Signal Service", "the customer portal's invoices and work orders"),
)


def invoice_adapters() -> tuple[Adapter, ...]:
    """One adapter for each vendor with an ``InvoiceFormat`` row: the row is the declaration."""
    from jason.community.invoice_formats import INVOICE_FORMATS

    vendors = dict.fromkeys(row.vendor for row in INVOICE_FORMATS)
    return tuple(Adapter(INVOICE_MODULE, vendor, "invoice, statement, or receipt layout") for vendor in vendors)


def adapters() -> tuple[Adapter, ...]:
    """Every declared adapter: the rows above, then the invoice layouts."""
    return ADAPTERS + invoice_adapters()


def allowed(module: str, term: str, rows: Iterable[Adapter]) -> bool:
    """Whether an adapter declared for ``module`` reads the layout of the vendor ``term`` names."""
    return any(row.module == module and row.names(term) for row in rows)


def declared(term: str, rows: Iterable[Adapter]) -> bool:
    """Whether any adapter is declared for the vendor ``term`` names."""
    return any(row.names(term) for row in rows)


def stale(root: Path, rows: Iterable[Adapter]) -> list[str]:
    """A line for each declaration the code no longer bears out: its module is gone, or the module no longer names the
    vendor. A stale row is removed, as a cleared term leaves the baseline."""
    found: list[str] = []
    sources: dict[str, str] = {}
    for row in rows:
        path = root / row.module
        if not path.is_file():
            found.append(f"{row.module}: no such module (adapter for {row.vendor})")
            continue
        if row.module not in sources:
            sources[row.module] = fold(path.read_text(encoding="utf-8"))
        if not any(fold(word) in sources[row.module] for word in (row.vendor, *row.signature)):
            found.append(f"{row.module}: does not name {row.vendor}")
    return found


def table(rows: Iterable[Adapter] | None = None) -> str:
    """The adapters as the Markdown table ``docs/adapters.md`` carries."""
    lines = ["| Vendor | Module | Reads |", "|---|---|---|"]
    for row in (ADAPTERS if rows is None else rows):
        lines.append(f"| `{row.vendor}` | `{row.module}` | {row.reads} |")
    return "\n".join(lines)


def unlisted(text: str, rows: Iterable[Adapter]) -> list[str]:
    """The adapters ``text`` (the adapters document) does not list: each needs a line that carries its vendor in a code
    span and, for a row declared here, its module."""
    lines = text.splitlines()
    missing: list[str] = []
    for row in rows:
        need = [f"`{row.vendor}`"] + ([f"`{row.module}`"] if row.module != INVOICE_MODULE else [])
        if not any(all(part in line for part in need) for line in lines):
            missing.append(f"{row.vendor} ({row.module})")
    return missing


def main() -> int:
    print(table())
    print()
    print("Invoice layouts (`" + INVOICE_MODULE + "`): " + ", ".join(f"`{row.vendor}`" for row in invoice_adapters()) + ".")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["Adapter", "ADAPTERS", "INVOICE_MODULE", "invoice_adapters", "adapters", "allowed", "declared", "stale", "table", "unlisted"]
