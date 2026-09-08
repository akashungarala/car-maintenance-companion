# Remote state in OCI Object Storage, via its S3-compatible API.
#
# Partial configuration: the bucket must exist before `tofu init`, so the
# endpoint and credentials are supplied at init time rather than committed:
#
#   tofu init -backend-config=backend.hcl -migrate-state
#
# State contains infrastructure detail and credentials, and must never be
# committed — `.gitignore` denies *.tfstate and backend.hcl for that reason.
terraform {
  backend "s3" {
    key = "car-maintenance-companion/prod.tfstate"

    # R2 is S3-compatible but is not S3; these checks do not apply to it.
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
    use_path_style              = true
  }
}
