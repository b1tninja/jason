# A local credential store for tenant credentials: research

Status: research notes (October 3, 2026), not a decision. Context: [install-design.md](install-design.md) puts secrets out of scope
for the first release; this is what a later phase could use. One dev PC now, many communities later.

## The finding that shapes everything

The "fake AWS" emulators are **test fixtures, not secret stores.** Using one as the place real tenant credentials live is the wrong
job for it. What they are good for is **API compatibility**: code written against the AWS Secrets Manager API runs unchanged against
an emulator in development and against real AWS Secrets Manager (or anything that speaks it) later. So the design question splits in two:

1. **The interface** jason codes against (a `SecretStore`): get, put, list, and delete by a tenant path.
2. **The backend** behind it, chosen per environment.

## The emulators (as of this research)

| Tool | License | Notes |
|---|---|---|
| LocalStack | proprietary since March 23, 2026 | `latest` needs an account and an auth token; the free tier is for non-commercial use. The open Community image was archived. Not a fit for a platform we may host. |
| Moto (server mode) | Apache 2.0 | Oldest (2013). In-memory; state is reset by design. Docker image `motoserver/moto`. Python test suites are its purpose. |
| MiniStack | MIT | 60+ services on port 4566, one container, about 110 MB slim. Secrets Manager covers create, get, put, version stages, rotate, restore, replicate, resource policies. Disk persistence is documented for S3 only. |
| Floci | MIT | Launched March 2026, the most starred of the new ones. Reported as ephemeral. |
| fakecloud | AGPL-3.0-or-later per its README (a third-party article says MIT; trust the README) | Claims 106 services and strict conformance. Persistence and encryption not documented where I read. |
| LocalEmu | not checked | Claims drop-in for LocalStack Community. |

What none of them promise: **encryption at rest, durable storage, or authentication by default** (fakecloud's request signing and IAM
checks are opt-in; MiniStack's access control is minimal unless `AUTH=true`). A third-party survey states that none is intended for
real, non-test secret storage. I did not verify each project's persistence myself; where a README was silent I say so above.

## What to do about it

- **Code to the AWS Secrets Manager API through `boto3`**, with the endpoint as a setting (`endpoint_url`). Tenant secrets are named
  by path: `jason/<community>/<name>`. Production can be real AWS Secrets Manager with per-tenant IAM policy on that prefix.
- **In dev and tests, point it at an emulator.** MiniStack or Moto in Docker: free, tiny, no account. Treat anything stored there as
  disposable. This is where the test suite can exercise the store without a cloud account.
- **For real secrets on the one dev PC, do not rely on the emulator.** Two honest options:
  - **The operating system's store** (Windows Credential Manager through the `keyring` package, which uses DPAPI): no server, bound to
    the Windows user, nothing in Docker. Fine for one PC and one person; poor for a service or many tenants.
  - **OpenBao or Vault in Docker, run in production mode** (not `-dev`, which is in-memory and loses everything on restart): real
    encryption at rest, a sealed state that needs an unseal after restart (or auto-unseal), policies, and a KV store per tenant path. It
    does not speak the AWS API, so it needs its own backend class. This is the one that grows into a multi-tenant platform without
    leaving the self-hosted world. Verify its namespace and policy features against the version chosen before relying on them.
- **Keep Keeper** as one more backend. It is what jason uses today.

So the shape is one interface with these backends: Keeper (today), AWS-API (emulator in dev or tests, real AWS in a hosted platform),
OS keyring (one PC), and OpenBao (self-hosted multi-tenant). The install guide's credential requirement reports which backend is
configured and whether it answers; nothing else in jason learns which.

## Facts about this machine

- Docker 29.3.1 is installed, but its engine was not running when checked (the Docker Desktop pipe was missing). Start Docker Desktop first.
- `boto3` and `keyring` are not installed in jason's environment; they would be optional extras (`[secrets]`).

## Not decided

- Whether tenant secrets belong in one store with a path per community, or one store per community. Per community is the stronger
  boundary and costs more to run.
- Which of the OS keyring and OpenBao the single PC should use first. The keyring is the least to run; OpenBao is the one that is
  not thrown away when a second community arrives.
- What jason must never hold: a secret value in a log, a manifest, a report, a console response, or a repository.
