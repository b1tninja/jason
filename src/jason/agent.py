"""Jason HOA agent — programmatic access to PayHOA, SMUD, and i-doxs."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from idoxs import IdoxsClient, SyncEngine
from idoxs.sync.models import SyncResult
from payhoa import PayhoaClient
from smud import SmudClient

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

    @property
    def org_id(self) -> int:
        return self.settings.payhoa_org_id

    def _vault_session(self) -> VaultSession:
        if self._vault is None:
            self._vault = VaultSession.from_settings(
                self.settings, interactive=self._interactive
            )
        return self._vault

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

    def sync_idoxs(
        self,
        *,
        full: bool = False,
        download_pdfs: bool = False,
        account: str | None = None,
    ) -> SyncResult:
        """Sync City of Sacramento bill history into the local idoxs cache.

        Default: Bills.aspx ACCOUNT=ALL, metadata only, skip pages already known.
        PDFs remain lazy unless download_pdfs=True.
        """
        client = self.idoxs()
        engine = SyncEngine(
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
        path: str | Path = "data/payhoa_txs.jsonl",
        *,
        reviewed: ReviewedFilter = False,
        search: str = "",
        raw: bool = False,
        fmt: Literal["jsonl", "json"] = "jsonl",
    ) -> Path:
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
        """SMUD then i-doxs (order matters for exclusive routing)."""
        return BillSourceRegistry(
            [
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
        )

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
        if self._vault is not None:
            self._vault.close()
            self._vault = None

    def __enter__(self) -> Jason:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
