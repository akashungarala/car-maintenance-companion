# Object storage for OpenTofu state and PostgreSQL backups.
#
# Oracle Always Free includes 10 GB of object storage, and OCI exposes an
# S3-compatible API, so CloudNativePG's Barman S3 support works against it
# unchanged.
#
# The honest caveat: this is the same provider as the cluster, so an account
# problem takes the backups with it (risk R1 — Oracle has already changed free
# tier terms once). It does survive the failure that actually happens, which is
# losing the node. A genuinely off-provider copy is tracked separately.

data "oci_objectstorage_namespace" "this" {
  compartment_id = var.compartment_ocid
}

resource "oci_objectstorage_bucket" "tofu_state" {
  compartment_id = var.compartment_ocid
  namespace      = data.oci_objectstorage_namespace.this.namespace
  name           = "cmc-tofu-state"
  access_type    = "NoPublicAccess"

  # State contains infrastructure detail and, because it records the customer
  # secret key below, credentials. Versioning means a corrupt or truncated
  # write is recoverable rather than terminal.
  versioning = "Enabled"
}

resource "oci_objectstorage_bucket" "pg_backups" {
  compartment_id = var.compartment_ocid
  namespace      = data.oci_objectstorage_namespace.this.namespace
  name           = "cmc-pg-backups"
  access_type    = "NoPublicAccess"

  # Deliberately no versioning and no retention rule, unlike the state bucket.
  #
  # OCI rejects the two together ("Cannot create retention rule since this
  # bucket has versioning enabled"), and for a backup bucket both are actively
  # wrong anyway:
  #
  #   versioning      — Barman prunes expired backups and WAL. Versioning would
  #                     retain every deleted object forever and quietly consume
  #                     the 10 GB Always Free allowance.
  #   retention rules — they make objects immutable for the duration, which
  #                     would *prevent* Barman from pruning at all.
  #
  # Lifecycle belongs to Barman's retentionPolicy on the Cluster resource. Bucket
  # size is worth alerting on in F8; that is the real backstop.
  # "Suspended", not "Disabled": OCI only accepts Enabled or Suspended on an
  # existing bucket — a bucket that has ever had versioning on cannot go back.
  # Suspended stops new versions being created, which is the behaviour wanted.
  versioning = "Suspended"
}

# S3-compatible credentials. CloudNativePG and the OpenTofu S3 backend both
# speak S3, not OCI's native API.
resource "oci_identity_customer_secret_key" "s3" {
  display_name = "cmc-s3-compat"
  user_id      = var.user_ocid
}

output "s3_endpoint" {
  description = "S3-compatible endpoint for the tenancy's object storage namespace."
  value       = "https://${data.oci_objectstorage_namespace.this.namespace}.compat.objectstorage.${var.region}.oraclecloud.com"
}

output "s3_access_key_id" {
  description = "Access key for the S3-compatible API."
  value       = oci_identity_customer_secret_key.s3.id
}

output "s3_secret_access_key" {
  description = "Secret for the S3-compatible API. Never echo this into a shell that is being recorded."
  value       = oci_identity_customer_secret_key.s3.key
  sensitive   = true
}

output "backup_bucket" {
  value = oci_objectstorage_bucket.pg_backups.name
}
