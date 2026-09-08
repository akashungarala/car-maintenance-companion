# Infrastructure

OpenTofu configuration for the production cluster: an Oracle Cloud Always Free
Ampere (arm64) instance running k3s, fronted by Cloudflare.

**Read [ADR-0002](../../docs/adr/0002-k3s-on-oracle-always-free.md) first.** It explains why this
provider, what Oracle changed in June 2026, and the migration path if the free tier degrades again.

## What this creates

| Resource                                   | Notes                                                                              |
| ------------------------------------------ | ---------------------------------------------------------------------------------- |
| VCN, internet gateway, route table, subnet | `10.0.0.0/16`, one public subnet                                                   |
| Security list                              | 22 and 6443 restricted to `admin_cidr`; 80/443 public; ICMP for path MTU discovery |
| Ampere A1 instance                         | 2 OCPU / 12 GB / 100 GB — the Always Free ceiling, enforced by variable validation |
| k3s                                        | Pinned version, installed by cloud-init, Traefik included                          |
| Cloudflare DNS                             | Proxied A records for the app and API hostnames                                    |

Everything above the cluster — Argo CD, cert-manager, Sealed Secrets, the applications — is
installed from git by Argo CD in F5, not from here.

## Cost

$0/month, and the variable validations exist to keep it that way: exceeding 2 OCPU, 12 GB, or the
200 GB block storage allowance silently converts the instance to a billable one. There is no
warning from Oracle when that happens.

## Prerequisites

1. **An Oracle Cloud account.** Sign-up requires a credit card for identity verification; Always
   Free resources are not charged against it. Upgrading to Pay As You Go is a separate, explicit
   action — do not do it accidentally.
2. **A Cloudflare account** with the domain's nameservers delegated to it.
3. **OpenTofu** ≥ 1.9 — `brew install opentofu`.

## Getting the credentials

### Oracle Cloud

Generate an API signing key and register it:

```bash
mkdir -p ~/.oci && chmod 700 ~/.oci
openssl genrsa -out ~/.oci/oci_api_key.pem 2048
chmod 600 ~/.oci/oci_api_key.pem
openssl rsa -pubout -in ~/.oci/oci_api_key.pem -out ~/.oci/oci_api_key_public.pem
```

In the OCI console → profile menu → **My profile** → **API keys** → **Add API key** → paste the
_public_ key. The dialog then shows a configuration preview containing `user`, `fingerprint`,
`tenancy` and `region` — those are four of the five values needed.

`compartment_ocid` can be the tenancy OCID (the root compartment) unless you have created others.

### Cloudflare

- **API token**: My Profile → API Tokens → Create Token → _Edit zone DNS_ template, scoped to the
  single zone. Not the Global API Key, which is account-wide and cannot be scoped.
- **Zone ID**: the domain's Overview page, right-hand column.

### Your address

```bash
echo "$(curl -s ifconfig.me)/32"
```

`admin_cidr` has a validation rule rejecting `0.0.0.0/0` — exposing SSH and the Kubernetes API to
the internet is not a default worth allowing.

## Running it

```bash
cd infra/tofu
cp terraform.tfvars.example terraform.tfvars   # then fill it in — gitignored
cp backend.hcl.example backend.hcl             # then fill it in — gitignored

tofu init -backend-config=backend.hcl
tofu plan
```

**Read the plan.** Then, rather than `tofu apply`:

```bash
../../scripts/oci-provision-retry.sh
```

### Why the retry script

Always Free Ampere capacity is scarce. A perfectly valid plan routinely fails with
**"Out of host capacity"** — that is not an error to fix, it is a queue to join. The script walks
every availability domain in the region, backs off, and retries, while stopping immediately on any
_other_ kind of failure so real problems are not buried under retries.

Expect this to take hours, sometimes days, in a contended region. Run it under `tmux` and leave it.
If it never succeeds, switch region or take the Hetzner fallback in ADR-0002 — the manifests do not
change, because that portability is the whole reason for k3s over OKE.

## After it succeeds

```bash
tofu output                       # public IP, URLs, and the AD that had capacity
tofu output -raw fetch_kubeconfig_command | bash
export KUBECONFIG=$PWD/kubeconfig
kubectl get nodes
```

The kubeconfig is gitignored. It is a cluster-admin credential — treat it as one.

## State

> **Currently local, not R2.** The S3 backend in `backend.tf` cannot initialise until the R2 bucket
> exists, and creating that bucket needs a _second_ Cloudflare token with R2 permissions — the token
> used here is deliberately scoped to `Zone:DNS:Edit` and nothing else. Rather than widen that token
> or block provisioning, state is temporarily local via a gitignored `backend_override.tf`.
>
> **This is a real risk while it lasts:** `terraform.tfstate` is on one machine and is not backed up.
> Losing it means re-importing resources by hand. Migrate during F6, which stands up R2 for database
> backups anyway:
>
> ```bash
> tofu init -backend-config=backend.hcl -migrate-state && rm backend_override.tf
> ```

State lives in Cloudflare R2 (S3-compatible, free, no egress fees) and contains infrastructure
details that must not be public. `.gitignore` denies `*.tfstate`, `terraform.tfvars`, `backend.hcl`
and `kubeconfig`; `gitleaks` runs over every commit as the backstop.

`.terraform.lock.hcl` **is** committed — provider versions must be reproducible.

## Known sharp edges

- **The instance is reachable but 80/443 hang.** Oracle's Ubuntu images ship an iptables ruleset
  whose INPUT chain ends in REJECT, so the OCI security list is necessary but not sufficient.
  cloud-init inserts ACCEPT rules ahead of it. If you rebuild the node by hand, do the same.
- **A newer Ubuntu image appears.** The image is resolved dynamically, so `lifecycle.ignore_changes`
  prevents a plan from proposing to destroy and recreate the node. Rebuilding is a deliberate act.
- **Single node.** Losing it loses the cluster. That is acceptable only because F6 puts database
  backups in R2, off the node. Until F6 lands, treat this cluster as disposable.
