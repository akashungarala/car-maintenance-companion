# Remote state in Cloudflare R2 (S3-compatible, 10 GB free, no egress fees).
#
# Partial configuration: the bucket must exist before `tofu init`, so the
# credentials and bucket name are supplied at init time rather than committed:
#
#   tofu init -backend-config=backend.hcl
#
# State contains the instance's private details and must never be committed —
# `.gitignore` denies *.tfstate for that reason.
terraform {
  backend "s3" {
    key = "car-maintenance-companion/prod.tfstate"

    region = "auto"

    # R2 is S3-compatible but is not S3; these checks do not apply to it.
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
    use_path_style              = true
  }
}
