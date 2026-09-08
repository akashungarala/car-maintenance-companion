# ---------------------------------------------------------------------------
# Oracle Cloud authentication
# ---------------------------------------------------------------------------

variable "tenancy_ocid" {
  description = "OCID of the Oracle Cloud tenancy."
  type        = string
}

variable "user_ocid" {
  description = "OCID of the API user."
  type        = string
}

variable "api_key_fingerprint" {
  description = "Fingerprint of the API signing key uploaded to the OCI user."
  type        = string
}

variable "api_private_key_path" {
  description = "Path to the OCI API private key on the machine running tofu."
  type        = string
  default     = "~/.oci/oci_api_key.pem"
}

variable "compartment_ocid" {
  description = "Compartment to create resources in. The tenancy OCID works as the root compartment."
  type        = string
}

variable "region" {
  description = <<-EOT
    OCI region, e.g. "us-ashburn-1".

    Choose deliberately: Always Free Ampere A1 capacity is scarce, and the
    home region of the tenancy is often the most contended. See risk R2 and
    scripts/oci-provision-retry.sh.
  EOT
  type        = string
}

# ---------------------------------------------------------------------------
# Compute — sized to the Always Free allocation
# ---------------------------------------------------------------------------

variable "instance_ocpus" {
  description = <<-EOT
    Ampere A1 OCPUs. The Always Free allocation was reduced from 4 OCPU / 24 GB
    to 2 OCPU / 12 GB on 15 June 2026 (ADR-0002). Exceeding it makes the
    instance billable.
  EOT
  type        = number
  default     = 2

  validation {
    condition     = var.instance_ocpus <= 2
    error_message = "Always Free allows at most 2 Ampere A1 OCPUs since 2026-06-15. Raising this makes the instance billable."
  }
}

variable "instance_memory_gbs" {
  description = "Ampere A1 memory. Always Free allows up to 12 GB (ADR-0002)."
  type        = number
  default     = 12

  validation {
    condition     = var.instance_memory_gbs <= 12
    error_message = "Always Free allows at most 12 GB since 2026-06-15. Raising this makes the instance billable."
  }
}

variable "boot_volume_gbs" {
  description = "Boot volume size. Always Free includes 200 GB of block storage in total."
  type        = number
  default     = 100

  validation {
    condition     = var.boot_volume_gbs >= 50 && var.boot_volume_gbs <= 180
    error_message = "Keep between 50 and 180 GB to stay inside the 200 GB Always Free block storage allowance."
  }
}

variable "availability_domain_index" {
  description = <<-EOT
    Which availability domain to attempt, 0-based.

    A1 capacity is frequently exhausted in a given AD ("Out of host capacity").
    The retry script walks this value across the region's ADs rather than
    failing on the first.
  EOT
  type        = number
  default     = 0
}

variable "ssh_public_key" {
  description = "SSH public key authorised on the instance."
  type        = string
}

# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

variable "admin_cidr" {
  description = <<-EOT
    CIDR permitted to reach SSH (22) and the Kubernetes API (6443).

    Defaulting this to 0.0.0.0/0 would expose the cluster API to the internet.
    Set it to your own address: `curl -s ifconfig.me`/32.
  EOT
  type        = string

  validation {
    condition     = var.admin_cidr != "0.0.0.0/0"
    error_message = "Refusing to expose SSH and the Kubernetes API to the whole internet. Set admin_cidr to your own address."
  }
}

variable "http_ingress_cidrs" {
  description = <<-EOT
    CIDRs permitted to reach 80/443. Open by default because Cloudflare's
    proxy fronts the origin; F9 narrows this to Cloudflare's published ranges
    so the origin cannot be reached directly.
  EOT
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# ---------------------------------------------------------------------------
# DNS
# ---------------------------------------------------------------------------

variable "cloudflare_api_token" {
  description = "Cloudflare API token with Zone:DNS:Edit on the zone."
  type        = string
  sensitive   = true
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone ID for the root domain."
  type        = string
}

variable "app_hostname" {
  description = "Hostname serving the application, e.g. garage.example.com."
  type        = string

  validation {
    condition     = length(split(".", var.app_hostname)) == 3
    error_message = "Use a single-label subdomain (host.example.com). Cloudflare's free Universal SSL does not cover deeper names, and the TLS handshake will fail."
  }
}

variable "api_hostname" {
  description = <<-EOT
    Hostname serving the API.

    MUST be a single label below the apex. Cloudflare's free Universal SSL
    certificate covers only `example.com` and `*.example.com`, and a wildcard
    matches one label — so `api.garage.example.com` is not covered and fails
    the TLS handshake outright. Multi-level wildcards need Advanced Certificate
    Manager, which is a paid add-on.
  EOT
  type        = string

  validation {
    condition     = length(split(".", var.api_hostname)) == 3
    error_message = "Use a single-label subdomain (host.example.com). Cloudflare's free Universal SSL does not cover deeper names, and the TLS handshake will fail."
  }
}

variable "k3s_version" {
  description = "Pinned k3s version. Unpinned installs are not reproducible."
  type        = string
  default     = "v1.31.4+k3s1"
}
