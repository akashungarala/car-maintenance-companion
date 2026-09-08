# Both records are proxied, so Cloudflare terminates TLS at the edge, absorbs
# volumetric attacks and hides the origin IP. Certificates are issued by
# cert-manager over DNS-01 rather than HTTP-01, which works through the proxy
# and supports wildcards.

resource "cloudflare_dns_record" "app" {
  zone_id = var.cloudflare_zone_id
  name    = var.app_hostname
  content = oci_core_instance.k3s.public_ip
  type    = "A"
  proxied = true
  ttl     = 1 # required to be 1 (automatic) when proxied
  comment = "Car Maintenance Companion — app ingress (managed by OpenTofu)"
}

resource "cloudflare_dns_record" "api" {
  zone_id = var.cloudflare_zone_id
  name    = var.api_hostname
  content = oci_core_instance.k3s.public_ip
  type    = "A"
  proxied = true
  ttl     = 1
  comment = "Car Maintenance Companion — API ingress (managed by OpenTofu)"
}
