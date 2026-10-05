"""Jason HOA agent — programmatic access to PayHOA, SMUD, and i-doxs."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from idoxs import IdoxsClient
from idoxs import SyncEngine as IdoxsSyncEngine
from idoxs.sync.models import SyncResult as IdoxsSyncResult
from payhoa import PayhoaClient
from smud import SmudClient
from smud import SyncEngine as SmudSyncEngine
from smud.sync.models import SyncResult as SmudSyncResult

from jason.config import Settings
from jason.idoxs_data import IdoxsBillMatch, IdoxsBillStore
from jason.payhoa_tx import (
    ReviewedFilter,
    dump_transactions,
    list_normalized_transactions,
    probe_transactions,
)
from jason.secrets import LoginCredentials, VaultSession, get_idoxs_credentials
from jason.smud_data import BillMatch, SmudBillStore
from jason.sources import (
    BillSourceRegistry,
    IdoxsBillSource,
    SmudBillSource,
    UploadReport,
)
from jason.sources.attach import attach_bills as run_attach_bills
from jason.catalog import PayhoaCatalog
from jason.community.secured_store import SecuredCatalog
from jason.community.tax_store import TaxStore
from jason.tasks.sync_characteristics import CharacteristicsSyncResult, sync_characteristics as run_sync_characteristics
from jason.tasks.sync_secured import SecuredSyncResult, sync_secured as run_sync_secured
from jason.tasks.sync_tax import TaxSyncResult, sync_tax as run_sync_tax
from jason.google import GoogleDocs, GoogleDrive, GoogleGmail, GoogleSheets, open_drive
from jason.tasks.sync_bills import (
    SyncBillsReport,
    list_pending_utility_transactions,
    sync_bills as run_sync_bills,
)
from payhoa.reports import iter_report_definitions
from jason.tasks.communications import CommunicationsReport, list_owner_communications
from jason.tasks.context_notes import ContextNotes, fetch_context_notes
from jason.tasks.request_actions import (
    attach_to_request,
    comment_on_request,
    note_on_request,
)
from jason.tasks.request_review import ReviewItem, review_requests
from jason.tasks.export_documents import DocumentExport, export_documents
from jason.tasks.export_requests import RequestExport, export_requests
from jason.tasks.request_sheet import (
    RequestSheet,
    attachment_columns,
    embed_sheet_photos,
    request_sheet_tabs,
    write_request_sheet,
)
from jason.tasks.publish_document import publish_google_doc as run_publish_google_doc
from jason.tasks.sync_catalog import CatalogSyncReport, sync_catalog
from jason.tasks.sync_request_files import RequestFilesReport, sync_request_files
from jason.tasks.vendor_match import VendorMatchReport, suggest_vendor_matches
from jason.tasks.violations_pull import ViolationsPullReport, pull_violations
from jason.tasks.who_owes import WhoOwesReport, who_owes
from jason.tasks.who_owes_sheet import WhoOwesSheetWrite, write_who_owes_sheet
from jason.tasks.upload_idoxs_bills import upload_idoxs_bills
from jason.tasks.upload_smud_bills import upload_smud_bills


class Jason:
    """HOA agent: Keeper-backed credentials, PayHOA/SMUD/i-doxs clients, bill matching."""

    def __init__(
        self,
        env_file: str | Path | None = None,
        *,
        interactive: bool = False,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or Settings.load(env_file)
        self._interactive = interactive
        self._vault: VaultSession | None = None
        self._payhoa: PayhoaClient | None = None
        self._smud: SmudClient | None = None
        self._idoxs: IdoxsClient | None = None
        self._bills: SmudBillStore | None = None
        self._idoxs_bills: IdoxsBillStore | None = None
        self._taxes: TaxStore | None = None
        self._secured: SecuredCatalog | None = None
        self._catalog: PayhoaCatalog | None = None
        self._drive: GoogleDrive | None = None
        self._portals: dict[str, Any] = {}

    @property
    def org_id(self) -> int:
        return self.settings.payhoa_org_id

    @property
    def community(self):
        """The active profile's association specification, separate from task code."""
        from jason.community import Community, community as active

        loaded: Community = active()
        return loaded

    def _vault_session(self) -> VaultSession:
        if self._vault is None:
            self._vault = VaultSession.from_settings(
                self.settings, interactive=self._interactive
            )
        return self._vault

    def vault_store(self):
        """The credential vault (``jason.vault``): Keeper, over this agent's one Keeper session."""
        from jason.vault.keeper import KeeperStore

        return KeeperStore.from_session(self._vault_session())

    def credential(self, integration: str, name: str):
        """A credential for the active community: its vault path first, else the Keeper record its ``.env`` key names
        (``jason.vault.resolver``; the fallback logs the key as deprecated). Fails fast with ``KeeperAuthRequired``
        when not interactive."""
        from jason.community.profile import profile_name
        from jason.vault.resolver import credential

        store = self.vault_store()
        return credential(profile_name(), integration, name, store=store, record_uids=self.settings.record_uids,
                          load_record=store.load_by_uid)

    def credentials(
        self, record_uid: str, *, require_totp: bool = False
    ) -> LoginCredentials:
        return self._vault_session().get_credentials(
            record_uid, require_totp=require_totp
        )

    def payhoa(self, *, site_id: int = 2) -> PayhoaClient:
        if self._payhoa is not None and self._payhoa.is_authenticated:
            return self._payhoa
        creds = self.credentials(
            self.settings.payhoa_record_uid, require_totp=True
        )
        assert creds.totp_code is not None
        client = PayhoaClient(site_id=site_id)
        client.login(creds.login, creds.password, totp_code=creds.totp_code)
        self._payhoa = client
        return client

    def payhoa_test(self, *, site_id: int = 2) -> PayhoaClient:
        """PayHOA as the unprivileged test owner (``payhoa_test_record_uid``): for trying a form from an owner's side.
        Its answers are never an owner's (``payhoa_test_membership_ids``)."""
        if not self.settings.payhoa_test_record_uid:
            raise ValueError("payhoa_test_record_uid is not set in .env")
        creds = self.credentials(self.settings.payhoa_test_record_uid)
        client = PayhoaClient(site_id=site_id)
        client.login(creds.login, creds.password, totp_code=creds.totp_code)
        return client

    def smud(self) -> SmudClient:
        if self._smud is not None:
            return self._smud
        if not self.settings.smud_record_uid:
            raise ValueError("smud_record_uid is not set in .env")
        creds = self.credentials(self.settings.smud_record_uid)
        client = SmudClient(creds.login, creds.password)
        # Multi-account portals: authenticate without selecting; callers use
        # select_account(account_number) per bill.
        client.login_accounts()
        self._smud = client
        return client

    def idoxs(self) -> IdoxsClient:
        if self._idoxs is not None and self._idoxs.is_authenticated:
            return self._idoxs
        if not self.settings.idoxs_record_uid:
            raise ValueError("idoxs_record_uid is not set in .env")
        creds = get_idoxs_credentials(
            settings=self.settings,
            interactive=self._interactive,
        )
        client = IdoxsClient(
            creds.username,
            creds.password,
            security_answers=creds.security_answers,
        )
        client.login()
        self._idoxs = client
        return client

    def drive(self, *, interactive: bool = False) -> GoogleDrive:
        """Google Drive client. Listing and download live in jason.google.

        ``interactive`` defaults to false. A missing token then raises
        ``GoogleAuthRequired`` instead of opening a browser.
        """
        if self._drive is None:
            self._drive = open_drive(
                self.settings,
                self._vault_session(),
                interactive=interactive,
            )
        return self._drive

    def photos(self):
        """Google Photos (Picker, and jason's own albums) on its own token; a first consent needs --interactive."""
        from jason.google.session import open_photos

        return open_photos(self.settings, self._vault_session(), interactive=self._interactive)

    def google_vault(self):
        """Google Vault (matters, legal holds) on its own token; a first consent needs --interactive."""
        from jason.google.session import open_vault

        return open_vault(self.settings, self._vault_session(), interactive=self._interactive)

    def google_tasks(self):
        """Google Tasks on its own token; a first consent needs --interactive."""
        from jason.google.session import open_tasks

        return open_tasks(self.settings, self._vault_session(), interactive=self._interactive)

    def docs(self, *, interactive: bool = False) -> GoogleDocs:
        """Docs client on the Drive sign-in. Edits use documents.batchUpdate."""
        return self.drive(interactive=interactive).docs()

    def gmail(self, *, interactive: bool = False) -> GoogleGmail:
        """Read-only Gmail client on the Drive sign-in."""
        return self.drive(interactive=interactive).gmail()

    def sheets(self, *, interactive: bool = False) -> GoogleSheets:
        """Sheets client on the Drive sign-in."""
        return self.drive(interactive=interactive).sheets()

    @property
    def bills(self) -> SmudBillStore:
        if self._bills is None:
            self._bills = SmudBillStore(
                self.settings.smud_db, self.settings.smud_bills_dir
            )
        return self._bills

    @property
    def idoxs_bills(self) -> IdoxsBillStore:
        if self._idoxs_bills is None:
            self._idoxs_bills = IdoxsBillStore(
                self.settings.idoxs_db, self.settings.idoxs_bills_dir
            )
        return self._idoxs_bills

    def find_bills(
        self,
        amount_cents: int,
        *,
        around: date | str | datetime,
        window_days: int = 7,
    ) -> list[BillMatch]:
        return self.bills.find_bills(
            amount_cents, around=around, window_days=window_days
        )

    def find_idoxs_bills(
        self,
        amount_cents: int,
        *,
        around: date | str | datetime,
        window_days: int = 7,
    ) -> list[IdoxsBillMatch]:
        return self.idoxs_bills.find_bills(
            amount_cents, around=around, window_days=window_days
        )

    def ensure_bill_pdf(self, bill: BillMatch) -> Path:
        return self.bills.ensure_bill_pdf(bill, self.smud())

    def ensure_idoxs_bill_pdf(self, bill: IdoxsBillMatch) -> Path:
        return self.idoxs_bills.ensure_bill_pdf(bill, self.idoxs())

    def sync_smud(
        self,
        *,
        full: bool = False,
        account: str | None = None,
    ) -> SmudSyncResult:
        """Sync SMUD bill history into the local smud cache."""
        client = self.smud()
        engine = SmudSyncEngine(
            client,
            self.settings.smud_db,
            self.settings.smud_bills_dir,
        )
        try:
            return engine.sync(
                full=full,
                account_numbers=[account] if account else None,
            )
        finally:
            engine.close()

    @property
    def taxes(self) -> TaxStore:
        if self._taxes is None:
            self._taxes = TaxStore(self.settings.tax_db)
        return self._taxes

    def sync_tax(self, *, parcel: str | None = None) -> TaxSyncResult:
        """Sync county property tax for community parcels into the local catalog."""
        from jason.community.tax import SacramentoCountyTax

        parcels = (parcel,) if parcel else self.community.parcels()
        return run_sync_tax(
            self.taxes,
            SacramentoCountyTax(),
            parcels,
            bills_dir=self.settings.tax_bills_dir,
        )

    @property
    def secured(self) -> SecuredCatalog:
        if self._secured is None:
            self._secured = SecuredCatalog(self.settings.secured_db)
        return self._secured

    def sync_secured(self, roll: str | Path, *, parcel: str | None = None) -> SecuredSyncResult:
        """Copy secured-roll rows for community parcels into their own catalog."""
        from jason.community.secured import SecuredRoll

        parcels = (parcel,) if parcel else self.community.parcels()
        return run_sync_secured(self.secured, SecuredRoll(roll), parcels)

    def sync_solar(self):
        """Pull the solar lease funds' UCC filings from the public index into the index cache."""
        from jason.community.index_cache import IndexCache
        from jason.community.recorder import Sacramento
        from jason.tasks.sync_solar import sync_solar as run_sync_solar

        program = self.community.solar_program()
        if program is None:
            raise ValueError("the specification names no solar program")
        with IndexCache(self.settings.ownership_db.parent / "index-cache.db") as cache:
            return run_sync_solar(cache, Sacramento.county_recorder, program)

    def sync_finance(self, *, year: int | None = None):
        """Fetch the year's budget against actual and the bank balances from PayHOA into data/payhoa/finance-<year>.json."""
        from datetime import date

        from jason.tasks.finance import snapshot

        return snapshot(self.payhoa(), self.settings.payhoa_org_id, self.settings.ownership_db.parent, year=year or date.today().year)

    def ingest_library(self, *, fetch: bool = False, model: str | None = None, refresh_text: bool = False):
        """Classify the PayHOA library, reading each file's text; ``fetch`` downloads what is not on disk, ``model`` names a local model."""
        from jason.community.content import ModelClassifier
        from jason.tasks.library import ingest

        root = self.settings.ownership_db.parent
        client = self.payhoa() if fetch else None
        classifier = ModelClassifier(model=model) if model is not None else None
        return ingest(self.community, root, client=client, org_id=self.settings.payhoa_org_id if fetch else None,
                      model=classifier, refresh_text=refresh_text)

    def lawlibrary(self):
        """The lawlibrary checkout as a statute source; it runs in its own environment."""
        from jason.sources.lawlibrary import LawLibrary

        return LawLibrary(self.settings.lawlibrary_home)

    def export_authorities(self):
        """Write the words of the law Jason relies on under data/authorities, one page per span, from lawlibrary."""
        from jason.tasks.export_authorities import export_authorities

        return export_authorities(self.lawlibrary(), self.settings.ownership_db.parent)

    def association_pages(self):
        """Write records.md (the 5200 inventory) and duties.md (the duty briefs) under the reports folder."""
        from jason.tasks.association_pages import write_association_pages
        from jason.tasks.property_history import load_association_record

        root = self.settings.ownership_db.parent
        record = load_association_record(self.community, root)
        return write_association_pages(
            self.community, root, root / "reports", laws=root.parent / "docs" / "laws", governing=record.governing,
            title=self.community.name,
        )

    def records_request(self, *, fetch_pages: bool = False, include_liens: bool = True):
        """The copy-order list: what the association's record names and no recorded copy on disk carries."""
        from jason.tasks.property_history import load_association_record
        from jason.tasks.records_request import build_records_request

        root = self.settings.ownership_db.parent
        recorder = None
        if fetch_pages:
            from jason.community.recorder import Sacramento

            recorder = Sacramento.county_recorder
        return build_records_request(
            self.community, root, load_association_record(self.community, root),
            out_dir=root / "reports", fetch_pages=fetch_pages, recorder=recorder, include_liens=include_liens,
        )

    def sync_liens(self, *, all_liens: bool = False):
        """Pull the mechanic's lien filings for the developers, the association, and every owner into the index cache.

        With ``all_liens`` every lien-family filing is fetched for the wide
        names too: the association's, the utility's, the courts', the tax
        agencies', and the loan defaults.
        """
        from jason.community.index_cache import IndexCache
        from jason.community.recorder import Sacramento
        from jason.tasks.sync_liens import LIEN_FILINGS, MECHANICS_FILINGS, lien_queries, sync_liens as run_sync_liens

        community = self.community
        queries = lien_queries(community, self.property_histories())
        with IndexCache(self.settings.ownership_db.parent / "index-cache.db") as cache:
            return run_sync_liens(
                cache, Sacramento.county_recorder, queries,
                project=community.index_project(), association=community.index_association(), developers=community.developers(),
                filings=LIEN_FILINGS if all_liens else MECHANICS_FILINGS,
            )

    def sync_characteristics(self, *, parcel: str | None = None) -> CharacteristicsSyncResult:
        """Copy the assessor's residential characteristics for the unit parcels into the local store."""
        from jason.community.assessor import SacramentoCountyAssessor
        from jason.community.characteristics import CharacteristicsStore

        parcels = (parcel,) if parcel else self.community.units()
        with CharacteristicsStore(self.settings.characteristics_db) as store:
            return run_sync_characteristics(store, SacramentoCountyAssessor(), parcels)

    def unit_characteristics(self):
        """Every stored unit record, by parcel digits. No network."""
        from jason.community.characteristics import CharacteristicsStore

        if not self.settings.characteristics_db.is_file():
            return {}
        with CharacteristicsStore(self.settings.characteristics_db) as store:
            return store.all()

    def sync_idoxs(
        self,
        *,
        full: bool = False,
        download_pdfs: bool = False,
        account: str | None = None,
    ) -> IdoxsSyncResult:
        """Sync City of Sacramento bill history into the local idoxs cache.

        Default: Bills.aspx ACCOUNT=ALL, metadata only, skip pages already known.
        PDFs remain lazy unless download_pdfs=True.
        """
        client = self.idoxs()
        engine = IdoxsSyncEngine(
            client,
            self.settings.idoxs_db,
            self.settings.idoxs_bills_dir,
        )
        try:
            return engine.sync(
                full=full,
                account_numbers=[account] if account else None,
                download_pdfs=download_pdfs,
                all_accounts=account is None,
            )
        finally:
            engine.close()

    @property
    def catalog(self) -> PayhoaCatalog:
        if self._catalog is None:
            self._catalog = PayhoaCatalog(self.settings.payhoa_catalog)
        return self._catalog

    def sync_catalog(
        self,
        *,
        kinds: tuple[str, ...] | list[str] | None = None,
        people_status: str = "active",
        violation_status: str = "",
    ) -> CatalogSyncReport:
        """Pull units, people, violations, requests, and documents into the catalog."""
        return sync_catalog(
            self.payhoa(),
            self.catalog,
            self.org_id,
            kinds=kinds,
            people_status=people_status,
            violation_status=violation_status,
        )

    def export_requests(
        self,
        dest: str | Path | None = None,
        *,
        statuses: tuple[str, ...] | None = None,
        form_name: str | None = None,
        refresh: bool = True,
    ) -> RequestExport:
        """Write one markdown file and an HTML file for pasting into email.

        Photos are copied down to an email size. ``refresh`` downloads
        attachments first. The originals stay in the request folders.
        """
        root = self.settings.payhoa_catalog.parent
        files = root / "payhoa-files"
        if refresh:
            self.sync_request_files()
        path = Path(dest) if dest else root / "payhoa-requests.md"
        return export_requests(
            self.catalog,
            self.org_id,
            path,
            files_dir=files,
            statuses=statuses,
            form_name=form_name,
        )

    def export_request_sheet(
        self,
        *,
        statuses: tuple[str, ...] = ("pending",),
        title: str = "Mystique open requests",
    ) -> RequestSheet:
        """Create a new spreadsheet of open requests, one tab per kind.

        Vendor rows stay together on each tab. Photos are resized copies
        stored in Drive and shown with an IMAGE formula.
        """
        root = self.settings.payhoa_catalog.parent
        rows = self.catalog.search_requests(
            self.org_id, statuses=statuses, limit=None
        )
        client = self.payhoa()
        names: dict[int, list[str]] = {}
        for row in rows:
            request_id = int(row["id"])
            _urls, labels = attachment_columns(
                client.request_files(self.org_id, request_id)
            )
            if labels:
                names[request_id] = labels
        tables = request_sheet_tabs(
            self.catalog,
            self.org_id,
            statuses=statuses,
            files=names,
        )
        report = write_request_sheet(self.sheets(interactive=self._interactive), title, tables)
        embed_sheet_photos(
            self.sheets(interactive=self._interactive),
            self.drive(interactive=self._interactive),
            report.spreadsheet_id,
            root / "payhoa-files" / "requests",
        )
        return report

    def embed_request_photos(self, spreadsheet_id: str) -> int:
        """Put resized request photos into an existing request spreadsheet."""
        root = self.settings.payhoa_catalog.parent
        return embed_sheet_photos(
            self.sheets(interactive=self._interactive),
            self.drive(interactive=self._interactive),
            spreadsheet_id,
            root / "payhoa-files" / "requests",
        )

    def export_documents(self, dest: str | Path | None = None) -> DocumentExport:
        path = Path(dest) if dest else self.settings.payhoa_catalog.parent / "payhoa-documents.json"
        return export_documents(
            self.catalog, self.org_id, path, client=self.payhoa()
        )

    def document_sync(self, *, interactive: bool = False) -> Any:
        """Classify Drive rule-folders against the catalog. Does not upload."""
        from jason.tasks.sync_drive_documents import (
            dry_run_sync_drive_documents,
            list_rule_drive_files,
            load_sync_rules,
        )

        rules = load_sync_rules()
        drive_files = list_rule_drive_files(self.drive(interactive=interactive), rules)
        payhoa_docs = self.catalog.search_documents(
            self.org_id, files_only=False, limit=None
        )
        return dry_run_sync_drive_documents(drive_files, payhoa_docs, rules=rules)

    def publish_google_doc(
        self,
        document_id: str,
        parent_id: int,
        dest: str | Path,
        *,
        file_name: str | None = None,
        interactive: bool = False,
    ) -> dict[str, Any]:
        """Export a Google Doc to PDF and upload it into a PayHOA folder."""
        return run_publish_google_doc(
            self.drive(interactive=interactive),
            self.payhoa(),
            org_id=self.org_id,
            document_id=document_id,
            parent_id=parent_id,
            dest=dest,
            file_name=file_name,
        )

    def list_reports(self) -> list[dict[str, Any]]:
        """Built-in PayHOA report catalog (name, key, and required criteria)."""
        return iter_report_definitions(self.payhoa().report_config())

    def who_owes(self) -> WhoOwesReport:
        return who_owes(self.payhoa(), self.org_id)

    def who_owes_sheet(
        self,
        *,
        spreadsheet_id: str | None = None,
        interactive: bool = False,
    ) -> WhoOwesSheetWrite:
        """Write unpaid/past-due rows into the configured Google Sheet for review.

        Does not submit accounts to a collection agency.
        """
        sheet_id = spreadsheet_id or self.settings.google_sheets_spreadsheet_id
        if not sheet_id:
            raise ValueError(
                "google_sheets_spreadsheet_id is empty; set it in .env"
            )
        report = self.who_owes()
        return write_who_owes_sheet(
            report,
            self.sheets(interactive=interactive),
            sheet_id,
        )

    def ownership_sheet(self, *, interactive: bool = False):
        """Create a new ownership spreadsheet from county records.

        Does not write the Membership workbook.
        """
        from jason.community.ownership import OwnershipStore
        from jason.tasks.ownership_sheet import collect_ownership, create_ownership_sheet

        community = self.community
        with OwnershipStore(self.settings.ownership_db) as store:
            rows = collect_ownership(community.parcels(), store)
        return create_ownership_sheet(
            self.sheets(interactive=interactive),
            f"{community.name} ownership",
            rows,
        )

    def county_tables(self, *, live: bool = False):
        """The five county tabs.

        ``live`` reads the assessor and the recorder, and stores the pinned
        deed chain. Otherwise the tabs come from the ownership and tax
        databases already on disk.
        """
        from jason.community.ownership import OwnershipHistory, OwnershipStore
        from jason.community.recorder import Sacramento
        from jason.community.tax_store import TaxStore
        from jason.tasks.county_report import (
            accounts_for,
            histories_on_file,
            ownership_on_file,
            report_tabs,
        )
        from jason.tasks.ownership_sheet import collect_ownership

        community = self.community
        with OwnershipStore(self.settings.ownership_db) as store:
            developers = community.developers()
            if live:
                ownership = collect_ownership(community.parcels(), store)
                history = Sacramento.county_recorder.history(
                    community.deed_numbers(),
                    developers=developers,
                )
                store.remember_pinned(history)
            else:
                ownership = ownership_on_file(store, community.parcels())
                history = store.pinned_history(developers=developers) or OwnershipHistory("", (), developers)
            unit_histories = histories_on_file(store, community.units(), developers=developers)
            with TaxStore(self.settings.tax_db) as taxes:
                common = accounts_for(taxes, community.common_areas())
                units = accounts_for(taxes, community.units())
        return report_tabs(ownership, history, common, units, unit_histories=unit_histories)

    def county_report(self, *, interactive: bool = False):
        """Publish the county tabs. Does not write the Membership workbook.

        The tables are built first. A missing Google sign-in fails after the
        deed chain has been stored.
        """
        from jason.tasks.county_report import create_county_report

        tabs = self.county_tables(live=True)
        return create_county_report(
            self.sheets(interactive=interactive),
            f"{self.community.name} county",
            tabs,
        )

    def unit_charts(self, *, interactive: bool = False):
        """Create a new spreadsheet that charts the unit numbering and the sales."""
        from jason.tasks.unit_charts import create_unit_chart_sheet, unit_chart_tabs

        tabs = unit_chart_tabs(self.community.unit_blocks(), self.property_histories())
        return create_unit_chart_sheet(
            self.sheets(interactive=interactive), f"{self.community.name} unit numbers and sales", tabs
        )

    def sales_charts(self, *, interactive: bool = False):
        """Create a new spreadsheet that charts the conveyance history."""
        from jason.tasks.sales_charts import create_sales_chart_sheet, sales_chart_tabs

        tabs = sales_chart_tabs(self.property_histories())
        return create_sales_chart_sheet(
            self.sheets(interactive=interactive), f"{self.community.name} conveyance history", tabs
        )

    def equity_charts(self, *, interactive: bool = False, spreadsheet_id: str = ""):
        """Create a spreadsheet of unit values, appreciation, and a per-unit lookup, or refresh one by id."""
        from jason.tasks.equity_charts import create_equity_chart_sheet, equity_chart_tabs

        tabs = equity_chart_tabs(
            self.property_histories(), characteristics=self.unit_characteristics(), plans=self.community.floor_plans(),
        )
        return create_equity_chart_sheet(
            self.sheets(interactive=interactive), f"{self.community.name} values and appreciation", tabs,
            spreadsheet_id=spreadsheet_id,
        )

    def association_record(self):
        """The association's record from the index cache. No network."""
        from jason.tasks.property_history import load_association_record

        return load_association_record(self.community, self.settings.ownership_db.parent)

    def property_histories(self):
        """Every unit parcel's history from the stores on disk. No network."""
        from jason.tasks.property_history import load_parcel_histories

        return load_parcel_histories(self.community, self.settings.ownership_db.parent)

    def property_history(
        self,
        *,
        out: str | Path | None = None,
        sheet: bool = False,
        spreadsheet_id: str = "",
        interactive: bool = False,
        charts: bool = True,
    ):
        """Write one Markdown report per parcel, and optionally publish the spreadsheet.

        The Markdown goes under ``data/reports/property-history`` unless ``out``
        says otherwise. With ``spreadsheet_id`` the existing spreadsheet is
        refreshed in place; otherwise a new one is created. The Membership
        workbook is not written. Only the spreadsheet needs Google.
        """
        from jason.tasks.property_history import (
            PropertyHistoryReport,
            create_property_sheet,
            governing_values,
            lien_values,
            load_association_record,
            merge_county_tabs,
            property_tabs,
            refresh_property_sheet,
            write_markdown,
        )

        histories = self.property_histories()
        association = load_association_record(self.community, self.settings.ownership_db.parent)
        title = f"{self.community.name} property history"
        folder = Path(out) if out else self.settings.ownership_db.parent / "reports" / "property-history"
        written = write_markdown(
            histories, folder, title=title, association=association,
            characteristics=self.unit_characteristics(), plans=self.community.floor_plans(), charts=charts,
            solar_program=self.community.solar_program(), community=self.community,
        )
        report = PropertyHistoryReport(len(histories), sum(1 for item in histories if item.open), written)
        if sheet or spreadsheet_id:
            tabs = property_tabs(histories)
            tabs["Liens and notices"] = lien_values(histories, association)
            tabs["Governing records"] = governing_values(association)
            tabs = merge_county_tabs(tabs, self.county_tables(live=False))
            client = self.sheets(interactive=interactive)
            if spreadsheet_id:
                report.spreadsheet_id, report.url, report.counts = refresh_property_sheet(client, spreadsheet_id, tabs)
            else:
                report.spreadsheet_id, report.url, report.counts = create_property_sheet(client, title, tabs)
        return report

    def pull_violations(self) -> ViolationsPullReport:
        return pull_violations(self.payhoa(), self.org_id)

    def context_notes(
        self, *, unit_id: int | None = None, membership_id: int | None = None
    ) -> ContextNotes:
        return fetch_context_notes(
            self.payhoa(),
            self.org_id,
            unit_id=unit_id,
            membership_id=membership_id,
        )

    def owner_communications(self, recipient_id: int) -> CommunicationsReport:
        return list_owner_communications(self.payhoa(), self.org_id, recipient_id)

    def vendor_matches(self) -> VendorMatchReport:
        return suggest_vendor_matches(self.payhoa(), self.org_id, reviewed=False)

    def comment_on_request(
        self,
        request_id: int,
        message: str,
        *,
        notify_owner: bool = True,
        notify_admins: bool = False,
    ):
        """Post a comment. The reporter and unit owners are notified unless turned off."""
        return comment_on_request(
            self.payhoa(),
            self.org_id,
            request_id,
            message,
            notify_owner=notify_owner,
            notify_admins=notify_admins,
        )

    def note_on_request(self, request_id: int, note: str, *, private: bool = True):
        """Post an internal note. Private notes stay off the owner thread."""
        return note_on_request(
            self.payhoa(), self.org_id, request_id, note, private=private
        )

    def attach_to_request(self, request_id: int, path: str | Path, *, notify: bool = False):
        """Attach a local file to a request. Does not notify the owner unless asked."""
        return attach_to_request(self.payhoa(), request_id, path, notify=notify)

    def sync_request_files(
        self, *, request_ids: list[int] | None = None
    ) -> RequestFilesReport:
        dest = self.settings.payhoa_catalog.parent / "payhoa-files"
        return sync_request_files(
            self.payhoa(),
            self.org_id,
            dest,
            catalog=self.catalog,
            request_ids=request_ids,
        )

    def review_requests(
        self, *, apply_tag: str | None = None, tag_color: str = "#7A64C8"
    ) -> list[ReviewItem]:
        return review_requests(
            self.catalog,
            self.payhoa(),
            self.org_id,
            apply_tag=apply_tag,
            tag_color=tag_color,
        )

    def list_pending_utility_transactions(self):
        """Unreviewed PayHOA txs that route to SMUD or i-doxs."""
        return list_pending_utility_transactions(
            self.payhoa(),
            self.bill_source_registry(),
            org_id=self.org_id,
        )

    def sync_bills(
        self,
        *,
        date_window_days: int = 7,
        dry_run: bool = False,
        approve: bool = False,
        skip_sync: bool = False,
        sources: list[str] | None = None,
    ) -> SyncBillsReport:
        """PayHOA-first: list pending utility txs, sync only needed portals, attach."""

        def _sync_source(name: str):
            if name == "smud":
                return self.sync_smud()
            if name == "idoxs":
                return self.sync_idoxs()
            if any(p.key == name for p in self.community.vendor_portals()):
                return self.sync_vendor_portal(name)
            raise ValueError(f"unknown bill source: {name}")

        return run_sync_bills(
            self.payhoa(),
            self.bill_source_registry(),
            sync_source=_sync_source,
            org_id=self.org_id,
            date_window_days=date_window_days,
            dry_run=dry_run,
            approve=approve,
            skip_sync=skip_sync,
            sources=sources,
        )

    def list_transactions(
        self,
        *,
        reviewed: ReviewedFilter = False,
        search: str = "",
        raw: bool = False,
    ) -> list[dict[str, Any]]:
        return list_normalized_transactions(
            self.payhoa(),
            self.org_id,
            reviewed=reviewed,
            search=search,
            smud_category_id=self.settings.smud_category_id,
            raw=raw,
        )

    def dump_transactions(
        self,
        path: str | Path | None = None,
        *,
        reviewed: ReviewedFilter = False,
        search: str = "",
        raw: bool = False,
        fmt: Literal["jsonl", "json"] = "jsonl",
    ) -> Path:
        """``path`` defaults to ``payhoa_txs.jsonl`` in the profile's data folder."""
        if path is None:
            path = self.settings.payhoa_catalog.parent / "payhoa_txs.jsonl"
        return dump_transactions(
            self.payhoa(),
            self.org_id,
            path,
            reviewed=reviewed,
            search=search,
            smud_category_id=self.settings.smud_category_id,
            raw=raw,
            fmt=fmt,
        )

    def probe_transactions(self) -> list[dict[str, Any]]:
        return probe_transactions(
            self.payhoa(),
            self.org_id,
            smud_category_id=self.settings.smud_category_id,
        )

    def bill_source_registry(self) -> BillSourceRegistry:
        """SMUD, then i-doxs, then each vendor portal with a Keeper record (order matters for exclusive routing)."""
        from jason.sources.fieldportals import VendorPortalBillSource

        sources: list[Any] = [
            SmudBillSource(
                self.bills,
                self.smud,
                category_id=self.settings.smud_category_id,
            ),
            IdoxsBillSource(
                self.idoxs_bills,
                self.idoxs,
                category_id=self.settings.idoxs_category_id,
            ),
        ]
        for portal in self.community.vendor_portals():
            if self.settings.record_uid(portal.key) and portal.platform.name == "FIELDPORTALS":
                sources.append(VendorPortalBillSource(portal, self.settings.payhoa_catalog.parent))
        return BillSourceRegistry(sources)

    def vendor_portal(self, key: str):
        """A signed-in client for the vendor portal ``key`` (``mystique/vendors.py``), from its Keeper record."""
        from jason.community.symbols import PortalPlatform
        from jason.fieldportals.client import FieldPortals
        from jason.secrets import get_vendor_credentials
        from jason.signalservice.client import SignalService

        if key in self._portals:
            return self._portals[key]
        portal = next((p for p in self.community.vendor_portals() if p.key == key), None)
        if portal is None:
            raise LookupError(f"no vendor portal {key!r} in the specification")
        if portal.platform not in (PortalPlatform.FIELDPORTALS, PortalPlatform.SIGNAL_SERVICE):
            raise LookupError(f"no client for {portal.platform}")
        creds = get_vendor_credentials(key, settings=self.settings, interactive=self._interactive)
        client = FieldPortals(portal.account) if portal.platform is PortalPlatform.FIELDPORTALS else SignalService(portal.account)
        client.login(creds.login, creds.password)
        self._portals[key] = client
        return client

    def citizen_access(self):
        """Sacramento Citizen Access (Accela), signed in with the Keeper record ``accela_record_uid``. Read-only: it
        pays no fee and schedules no inspection."""
        from jason.community.accela import AccelaError, SacramentoCitizenAccess
        from jason.secrets import get_accela_credentials

        creds = get_accela_credentials(settings=self.settings, interactive=self._interactive)
        client = SacramentoCitizenAccess()
        if not client.sign_in(creds.login, creds.password):
            raise AccelaError("Citizen Access refused the Keeper login")
        return client

    def postscanmail(self):
        """The read-only PostScanMail client, with the API key from the vault (``postscanmail/api-key``), else the
        Keeper record ``postscanmail_record_uid`` (its password field)."""
        from jason.postscanmail.client import PostScanMail
        from jason.vault.resolver import CredentialMissing

        try:
            secret = self.credential("postscanmail", "api-key")
        except CredentialMissing as exc:
            raise ValueError(f"no PostScanMail API key: {exc}") from None
        return PostScanMail(secret.first("api_key", "password"))

    def sync_mail(self, *, full: bool = False, log: Any = None) -> dict[str, int]:
        """Sync the association's PostScanMail mailbox to ``data/mail``: records, scans, text, and the sort."""
        from jason.tasks.mail import sync

        with self.postscanmail() as client:
            return sync(client, self.settings.payhoa_catalog.parent, full=full, log=log, community=self.community)

    def zoom(self):
        """The Zoom client for the association's account, from the Server-to-Server OAuth app in the vault
        (``zoom/app``), else the Keeper record ``zoom_record_uid`` (custom fields account_id, client_id,
        client_secret)."""
        from jason.vault.resolver import CredentialMissing
        from jason.zoom.client import Zoom, ZoomCredentials

        try:
            secret = self.credential("zoom", "app")
        except CredentialMissing as exc:
            raise ValueError(f"no Zoom app: {exc}") from None
        # The client secret is a custom field, or the record's password field (where `jason zoom --store-app` puts it).
        fields = {"client_secret": secret.get("password", ""), **{k: v for k, v in secret.items() if k != "password"}}
        return Zoom(ZoomCredentials.from_fields({k: v for k, v in fields.items() if v}))

    def store_zoom_app(self, account_id: str, client_id: str, client_secret: str = "") -> str:
        """Put the Zoom Server-to-Server OAuth app in a new Keeper login record and return its UID: the account id and
        client id as custom fields, the client secret (empty until a person fills it) in the password field."""
        return self._vault_session().create_login_record(
            "Zoom Server-to-Server OAuth app (jason)",
            password=client_secret,
            login=client_id,
            url="https://marketplace.zoom.us/user/build",
            custom={"account_id": account_id, "client_id": client_id},
            notes="The association's Zoom app for jason (docs/zoom.md). Put the app's client secret in the password field. "
                  "Jason reads it as zoom_record_uid.",
        )

    def store_google_client(self, client_id: str, client_secret: str, *, title: str, project_id: str = "",
                            notes: str = "") -> str:
        """Put a Google OAuth client in a new Keeper login record and return its UID: the client id as the login and as
        the custom field ``client_id``, the secret in the password field (``jason sign-in --import-client``)."""
        return self._vault_session().create_login_record(
            title,
            password=client_secret,
            login=client_id,
            url=f"https://console.cloud.google.com/auth/clients?project={project_id}" if project_id else "",
            custom={"client_id": client_id, **({"project_id": project_id} if project_id else {})},
            notes=notes,
        )

    def sync_zoom(self, *, full: bool = False, since=None, media: bool = False, log: Any = None) -> dict[str, int]:
        """Sync the Zoom account's meetings, transcripts, chats, and AI Companion summaries to ``data/zoom``."""
        from jason.tasks.zoom import sync

        with self.zoom() as client:
            return sync(client, self.settings.payhoa_catalog.parent, self.community, full=full, since=since, media=media, log=log)

    def schedule_hearing(self, plan) -> dict[str, Any]:
        """Create the hearing's Zoom meeting and keep what its notice may carry (never the host's start link)."""
        from jason.zoom.models import zoom_details

        with self.zoom() as client:
            plan.zoom = zoom_details(client.create_meeting(plan.meeting_body()))
        return plan.zoom

    def schedule_board_meeting(self, plan) -> dict[str, Any]:
        """Create the board meeting's Zoom meeting and keep what its notice may carry (never the host's start link)."""
        from jason.zoom.models import zoom_details

        with self.zoom() as client:
            plan.zoom = zoom_details(client.create_meeting(plan.meeting_body()))
        return plan.zoom

    def control_recording(self, meeting_id: int | str, method: str, *, by: str = "") -> dict[str, Any]:
        """Start, pause, resume, or stop the cloud recording of a live meeting, as the host, and log the act."""
        from jason.tasks.zoom import RECORDING_METHODS, record_live_act

        if method not in RECORDING_METHODS:
            raise ValueError(f"recording method is one of {', '.join(RECORDING_METHODS)}")
        with self.zoom() as client:
            client.in_meeting_control(meeting_id, f"recording.{method}")
        return record_live_act(self.settings.payhoa_catalog.parent, meeting_id, "recording", method, by=by)

    def caption(self, meeting_id: int | str, text: str, *, lang: str = "en-US", by: str = "") -> dict[str, Any]:
        """Post one line into the live meeting's captions, prefixed so everyone sees who wrote it, and log it."""
        from jason.tasks.zoom import record_live_act

        line = f"jason: {text.strip()}"
        act = record_live_act(self.settings.payhoa_catalog.parent, meeting_id, "caption", line, by=by)
        with self.zoom() as client:
            client.post_caption(client.caption_token(meeting_id), act["seq"], line, lang=lang)
        return act

    def sync_vendor_portal(self, key: str, *, full: bool = False, log: Any = None):
        """Sync one vendor portal to ``data/vendors/<key>``: account, visits, products, files, and checked invoices."""
        from jason.community.symbols import PortalPlatform
        from jason.tasks.vendor_portals import sync_portal

        portal = next(p for p in self.community.vendor_portals() if p.key == key)
        if portal.platform is PortalPlatform.SIGNAL_SERVICE:
            from jason.tasks.signal_service import sync_signal

            return sync_signal(self.vendor_portal(key), portal, self.settings.payhoa_catalog.parent, full=full, log=log)
        return sync_portal(self.vendor_portal(key), portal, self.settings.payhoa_catalog.parent, full=full, log=log)

    def attach_bills(
        self,
        *,
        date_window_days: int = 7,
        dry_run: bool = False,
        approve: bool = False,
        sources: list[str] | None = None,
    ) -> UploadReport:
        """Match unapproved PayHOA txs to registered bill sources and upload PDFs."""
        registry = self.bill_source_registry()
        if sources:
            registry = registry.filter(set(sources))
        return run_attach_bills(
            self.payhoa(),
            registry,
            org_id=self.org_id,
            date_window_days=date_window_days,
            dry_run=dry_run,
            approve=approve,
        )

    def upload_smud_bills(
        self,
        *,
        date_window_days: int = 7,
        dry_run: bool = False,
        approve: bool = False,
    ) -> UploadReport:
        return upload_smud_bills(
            self.payhoa(),
            self.bills,
            smud_client_factory=self.smud,
            org_id=self.org_id,
            date_window_days=date_window_days,
            dry_run=dry_run,
            approve=approve,
            smud_category_id=self.settings.smud_category_id,
        )

    def upload_idoxs_bills(
        self,
        *,
        date_window_days: int = 7,
        dry_run: bool = False,
        approve: bool = False,
    ) -> UploadReport:
        return upload_idoxs_bills(
            self.payhoa(),
            self.idoxs_bills,
            idoxs_client_factory=self.idoxs,
            org_id=self.org_id,
            date_window_days=date_window_days,
            dry_run=dry_run,
            approve=approve,
            category_id=self.settings.idoxs_category_id,
        )

    def close(self) -> None:
        if self._payhoa is not None:
            self._payhoa.close()
            self._payhoa = None
        if self._smud is not None:
            self._smud.close()
            self._smud = None
        if self._idoxs is not None:
            self._idoxs.close()
            self._idoxs = None
        if self._bills is not None:
            self._bills.close()
            self._bills = None
        if self._idoxs_bills is not None:
            self._idoxs_bills.close()
            self._idoxs_bills = None
        if self._taxes is not None:
            self._taxes.close()
            self._taxes = None
        if self._secured is not None:
            self._secured.close()
            self._secured = None
        if self._catalog is not None:
            self._catalog.close()
            self._catalog = None
        for client in self._portals.values():
            client.close()
        self._portals = {}
        if self._vault is not None:
            self._vault.close()
            self._vault = None

    def __enter__(self) -> Jason:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
