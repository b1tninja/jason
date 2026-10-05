# A practical, low-cost deployment: research

Status: research notes (October 3, 2026). Nothing here is decided or built. Prices come from third-party summaries of vendor pricing
pages and move often; re-check the vendor's page before committing. Figures marked *(general knowledge)* I did not look up in this
research.

## What jason is, for deployment purposes

These facts drive every choice below (read from the repository, not from a vendor):

- **A Flask app under waitress** (`jason-web`, the `web` extra) plus a React bundle, an MCP server, and a CLI of scheduled jobs.
- **Stateful on local disk.** About 109 modules use SQLite, around a dozen database files, and the data root holds hundreds of MB of
  documents (the library about 345 MB and PayHOA files about 193 MB on this PC). A "store lock" and a GPU lock are local file locks.
  So: one writer per community's data folder, and a container with no persistent volume loses it.
- **One data folder per community** (`<data root>/<profile>/`), which is the natural unit of tenancy.
- **Heavy, bursty work:** OCR (Tesseract), Chromium captures of vendor portals (Playwright), and model calls. None of these belongs in
  the always-on web process.
- **Models:** a local Ollama model for OCR, reading scans, and classification. The readers already sit behind a common shape (an Ollama
  reader and a Claude reader share one answer parser), so a hosted model is one more reader, not a rewrite.
- **Google** is used as an API (Drive, Docs, Sheets, Gmail, Tasks, Vault), reached over OAuth. It does not need to run on Google's cloud.

## Compute: the options, with costs

| Option | Monthly cost | Fit |
|---|---|---|
| **A small VM running Docker Compose** (Lightsail instance, or EC2 ARM) | Lightsail $5 (0.5 GB), $7 (1 GB) and up; EC2 `t4g.small` around $12 *(general knowledge)* | Cheapest. Runs the web app, a reverse proxy for HTTPS, and cron-style jobs on one box with one disk. Needs patching and a backup plan. |
| **Lightsail container service** | Nano $7 (0.25 vCPU, 0.5 GB), Micro $10, Small $15, Medium $40 | Managed and cheap, but small and with no persistent disk for SQLite. Fine for a stateless front end only. |
| **ECS on Fargate** | ARM 1 vCPU / 2 GB about $29; 0.5 vCPU / 1 GB about $14 (computed from $0.03238 per vCPU-hour and $0.00356 per GB-hour); Spot about 70% less but can be reclaimed | The "right" container platform, billed per second. Add an Application Load Balancer, about $16 a month before traffic *(general knowledge)*, which is the hidden cost for a tiny service. Persistent storage is an EBS volume attached to one task (since 2024) or EFS. |
| **ECS Express Mode** | Fargate plus the load balancer it provisions | AWS's replacement for App Runner. It sets up the cluster, load balancer, TLS, networking, scaling and logs for you. |
| **AWS App Runner** | n/a | **Closed to new customers on April 30, 2026.** Rule it out. |
| **Elastic Beanstalk** | the EC2 it runs (a single-instance environment needs no load balancer) | Still maintained in 2026 (new platform releases, a GitHub Actions deploy, Bedrock-based health analysis). Docker single-container works. An older model than ECS, but it is the least-assembly route to "an EC2 instance that deploys from CI." |
| **ECR** | storage about $0.10 per GB-month *(general knowledge)* | The image registry for ECS or Beanstalk. A few images cost cents. |

The decision that matters is not the service name. It is **where the SQLite files live**:

- **EFS** (a network file system) is the easy way to give a container a persistent disk, but SQLite's locking over NFS is a known
  weak spot; do not put live SQLite on it without testing.
- **An EBS volume** attached to a single Fargate task or EC2 instance is a real local disk with snapshots. It fits SQLite, and it
  means one writer per volume, which matches how jason locks its stores.
- **Replicating SQLite to S3** (Litestream) gives continuous backup of each database for pennies. I found no source in this research
  that confirms details of it on Fargate; test before relying on it.
- **Moving the stores to Postgres** is the multi-tenant answer but is a large change here (109 modules touch SQLite). RDS
  `db.t4g.micro` is about $12 a month; Aurora Serverless v2 can now scale to zero ACUs (resume about 15 seconds) and then costs only
  storage while idle. Not for now.

## Tenancy shape and what it costs

- **One shared app, one data folder per community, one volume.** Cheapest (one VM serves several communities) and matches the data
  layout today. The blast radius is the whole machine, and a bad query or a stuck job affects every community on it.
- **One task or VM per community ("cells").** Strong isolation and simple data movement, at $14 to $30 a month of compute per
  community before the load balancer. A shared load balancer across cells spreads its cost.
- Start with the first and keep the second possible, which is what the data layout and the per-community sign-in clients already do.

## The model: Bedrock in place of the local model

- **Prices (per million input / output tokens), from third-party pages:** Claude Haiku 4.5 $1 / $5; Claude Sonnet 4.6 $3 / $15;
  Claude Sonnet 5 $2 / $10 (the page I read gave conflicting accounts of whether that rate is permanent); Qwen3 VL 235B (text and
  vision) $0.53 / $2.66; Qwen3 32B $0.15 / $0.60.
- **Capabilities:** Claude on Bedrock keeps vision, PDF input, tool use, prompt caching, and extended thinking. The Converse API gives
  one request shape across providers, so a reader can swap models by configuration.
- **Privacy:** AWS says Bedrock does not store or log prompts and completions, does not use them to train models, and does not share
  them with the model providers. That is the property the board's private facts need. Cross-region inference profiles can keep a
  request in one geography; choose in-region or geographic, not global, if residency matters.
- **Cost feel (my arithmetic, not a source):** a scanned page is on the order of a couple thousand input tokens, so reading a 100-page
  instrument with a small model is cents to tens of cents. A monthly volume of a few hundred pages is single dollars. Measure with
  the extraction scorecard before trusting this.
- **Does not transfer:** the model trials on this PC (in `docs/document-tools.md`) were for one local model. A hosted Qwen is a
  different, larger model and Claude is a different family. Each needs its own row in the trials table and a run of the scorecard.
- **Beyond reading:** the local stack also uses an embedding model and AnythingLLM for chat over the library. Bedrock has embedding
  models, but AnythingLLM itself would need hosting or replacing. That is a separate piece of work.
- **Development:** keep Ollama locally and Bedrock in the cloud, behind the same reader shape. The emulators below do not run models.

## Secrets: services and development emulators

- **AWS Secrets Manager:** $0.40 per secret per month plus $0.05 per 10,000 calls, with a one-time $200 credit for accounts made after
  July 15, 2025. A secret can hold a JSON object, so one secret per community (many keys in it) costs $0.40 each, not per key.
- **SSM Parameter Store, standard tier:** free for up to 10,000 parameters of 4 KB; a SecureString costs only the KMS use. No rotation
  or resource policies. For a handful of communities this is the cheapest correct store.
- **Google Secret Manager** (if on Google's cloud): $0.06 per active version per location per month, six versions and 50,000 accesses
  free.
- **Development without AWS:** see [credential-store-research.md](credential-store-research.md). In short: MiniStack (MIT) or Moto
  (Apache 2.0) in Docker speak the Secrets Manager API (Moto also covers Parameter Store) and are fine for tests; LocalStack now needs
  an account and token. They are not secret stores, so nothing real goes in them.

## Does Google's cloud make sense?

For compute, no particular advantage. Drive, Docs, Sheets and Gmail are reached over OAuth from anywhere. What changes the answer is
the **OAuth and verification model**, which applies on any cloud:

- `drive.readonly`, broad Gmail scopes and similar are **restricted scopes**. An app serving users in other organizations must pass a
  Google security assessment (CASA) at roughly $500 to $4,500, renewed yearly, per the sources I read.
- **Domain-wide delegation** is per Workspace domain: each customer's super admin would authorize it. It does not scale to many
  customers, as the sources note.
- jason already points the other way: **each community uses its own OAuth client in its own Cloud project** (`jason sign-in
  --import-client`). A community's own client, used within its own organization, avoids the public verification path. This is
  worth confirming with Google's current rules before relying on it, but it suggests the multi-tenant model stays "bring your own
  Google client" rather than "one verified jason app."
- If Google's cloud were chosen: **Cloud Run** is cheap (free tier of 2 million requests; an always-on 1 vCPU instance about $13
  idle-billed) but has no persistent local disk (volumes are Cloud Storage or NFS; I did not verify details), which is worse for
  SQLite than an EC2 or Fargate volume. **Compute Engine** with a persistent disk is the equivalent of the VM option. **Vertex AI**
  would replace Bedrock. Workload identity lets AWS workloads call Google APIs without a stored key.

Mixing clouds is fine (AWS compute and models, Google APIs over OAuth). Choosing Google's cloud buys nothing the Drive use needs.

## A practical path, cheapest first

1. **Now:** the one PC, as it is. Add a `SecretStore` and a Bedrock reader only when the hosted step is real.
2. **First hosted step (one to three communities):** one ARM VM (Lightsail or EC2) running Docker Compose: jason-web, a reverse proxy
   for HTTPS, and scheduled jobs; data on the instance's disk with daily snapshots and an S3 copy; secrets in SSM Parameter Store;
   Bedrock through the instance's IAM role; Chromium and OCR jobs run as separate short containers. Roughly **$15 to $30 a month plus
   model use**, with no load balancer and no database service.
3. **When one machine is not enough:** ECS on Fargate or ECS Express Mode, a task and EBS volume per community or group of
   communities, Secrets Manager per community, and Postgres only if a shared store becomes necessary. Expect **$35 to $60 a month per
   cell with a load balancer** before storage and models.
4. **Decide later:** per-community cells or one shared app; whether AnythingLLM stays; whether to move off SQLite.

## Not verified

- Load balancer, EC2, and ECR prices *(general knowledge)*; whether ECS Express Mode shares one load balancer across services.
- Litestream on Fargate; EFS and SQLite locking beyond the general caution; Cloud Run volume behavior.
- Whether a community's own OAuth client fully avoids Google's verification for the scopes jason uses.
- Whether the current Bedrock model list includes the exact models jason's trials would need, and each one's vision quality on scans.

## Sources

- [LocalStack pricing change](https://blog.localstack.cloud/2026-upcoming-pricing-changes/)
- [AWS App Runner closed to new customers](https://bex.co/blog/2026/07/08/aws-app-runner-closes-new-customers) and [migration to ECS Express Mode](https://dev.to/ustun/a-practical-guide-to-moving-from-aws-app-runner-to-ecs-express-mode-1fe3)
- [Fargate pricing](https://www.factualminds.com/blog/amazon-fargate-ecs-task-pricing-2026/)
- [ECS storage options (EBS, EFS)](https://docs.aws.amazon.com/AmazonECS/latest/userguide/using_data_volumes.html)
- [Lightsail pricing](https://cloudburn.io/blog/amazon-lightsail-pricing) and [Elastic Beanstalk release notes](https://docs.aws.amazon.com/elasticbeanstalk/latest/relnotes/release-2026-07-16-al2.html)
- [Bedrock pricing](https://www.cloudzero.com/blog/amazon-bedrock-pricing/) and [Qwen3 VL on Bedrock](https://calculator.holori.com/llm/bedrock/qwen.qwen3-vl-235b-a22b)
- [Bedrock data protection](https://maturitymodel.security.aws.dev/en/4.-optimized/gen-ai-security/)
- [Secrets Manager pricing](https://cloudburn.io/blog/aws-secrets-manager-pricing) and [Parameter Store](https://docs.amazonaws.cn/en_us/systems-manager/latest/userguide/systems-manager-parameter-store.md)
- [Cloud Run pricing](https://cloud.google.com/run/pricing) and [Secret Manager pricing](https://cloud.google.com/secret-manager/pricing)
- [Google CASA and restricted scopes](https://deepstrike.io/blog/google-casa-security-assessment-2025) and [domain-wide delegation limits](https://www.unipile.com/gmail-api-service-account-domain-wide-delegation/)
- [Aurora Serverless v2 scale to zero](https://awsglossary.org/terms/aurora-serverless) and [RDS db.t4g.micro](https://www.bytebase.com/dbcost/rds/instance/db.t4g.micro/)
