"""Catalog upsert and PayHOA sync orchestration."""

from jason.catalog import PayhoaCatalog
from jason.tasks.sync_catalog import sync_catalog


class _FakePayhoa:
    def iter_units(self, org_id):
        assert org_id == 1
        yield {
            "id": 10,
            "title": "Lot 1",
            "balance": 0,
            "pastDueBalance": 50,
            "address": {
                "line1": "1 Main",
                "city": "Sacramento",
                "region": "California",
                "postalCode": "95814",
            },
        }

    def list_unit_contacts(self, unit_id):
        assert unit_id == 10
        return [{"id": 70, "name": "Tenant Person", "email": "tenant@example.com", "phone": "", "createdAt": "2025-01-02"}]

    def iter_people(self, org_id, status="active"):
        assert status == "active"
        yield {
            "id": 20,
            "userId": 30,
            "email": "owner@example.com",
            "isAdmin": False,
            "balance": 0,
            "profile": {"givenNames": "Ada", "familyName": "Lovelace"},
        }

    def iter_violations(self, org_id, status="All Outstanding", filters=None):
        yield {
            "id": 40,
            "unitId": 10,
            "status": "Pending",
            "title": "Fence",
            "reportedAt": "2026-01-02",
        }

    def list_forms(self):
        return [{"id": 7, "organizationId": 1, "name": "Inquiry"}]

    def list_form_submissions(self, form_id):
        assert form_id == 7
        return [
            {
                "id": 70,
                "organizationId": 1,
                "formId": 7,
                "unitId": 10,
                "membershipId": 20,
                "status": "open",
                "createdAt": "2026-02-01",
            }
        ]

    def list_documents(self, org_id):
        return [
            {
                "id": 90,
                "parentId": None,
                "fileName": "budget.pdf",
                "path": "budget.pdf",
                "directory": False,
                "public": 1,
                "fileSize": 12,
            }
        ]


def test_sync_catalog_upserts_all_kinds(tmp_path):
    catalog = PayhoaCatalog(tmp_path / "payhoa.db")
    report = sync_catalog(_FakePayhoa(), catalog, 1)
    assert report.errors == []
    assert report.summary().startswith("units=1 people=1")
    counts = catalog.counts(1)
    assert counts == {
        "units": 1,
        "people": 1,
        "violations": 1,
        "requests": 1,
        "documents": 1,
        "unit_contacts": 1,
    }
    row = catalog._conn.execute(
        "SELECT label, address_line1, city FROM units WHERE id = 10"
    ).fetchone()
    assert tuple(row) == ("Lot 1", "1 Main", "Sacramento")
    person = catalog._conn.execute("SELECT name, email FROM people").fetchone()
    assert tuple(person) == ("Ada Lovelace", "owner@example.com")
    request = catalog._conn.execute(
        "SELECT form_name, status FROM requests"
    ).fetchone()
    assert tuple(request) == ("Inquiry", "open")
    catalog.close()


def test_sync_catalog_records_kind_errors(tmp_path):
    class _Boom(_FakePayhoa):
        def iter_units(self, org_id):
            raise RuntimeError("units down")

    catalog = PayhoaCatalog(tmp_path / "payhoa.db")
    report = sync_catalog(_Boom(), catalog, 1, kinds=["units", "documents"])
    assert report.units == 0
    assert report.documents == 1
    assert report.errors == ["units: units down"]
    catalog.close()


def test_a_units_other_contacts_are_replaced_so_a_departed_tenant_is_gone(tmp_path):
    catalog = PayhoaCatalog(tmp_path / "payhoa.db")
    catalog.replace_unit_contacts(1, 10, [{"id": 1, "name": "Old Tenant"}, {"id": 2, "name": "Manager Co"}])
    catalog.replace_unit_contacts(1, 11, [{"id": 3, "name": "Other Unit"}])
    catalog.replace_unit_contacts(1, 10, [{"id": 2, "name": "Manager Co"}])         # the tenant left
    assert [c["name"] for c in catalog.unit_contacts(1, 10)] == ["Manager Co"]
    assert len(catalog.unit_contacts(1)) == 2
    catalog.close()
