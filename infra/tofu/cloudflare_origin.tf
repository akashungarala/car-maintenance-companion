# Restrict the origin to Cloudflare.
#
# Cloudflare proxies every hostname, so nothing legitimate reaches 80/443 from
# anywhere else. Leaving them open to the world means the origin IP -- which
# leaks through certificate transparency logs, old DNS records, and scanning --
# can be hit directly, bypassing Cloudflare's TLS, WAF and DDoS protection
# entirely. It also makes CF-Connecting-IP forgeable, and the rate limiter
# trusts that header to identify callers.
#
# Fetched at apply time rather than hardcoded. Cloudflare adds ranges
# occasionally, and a stale hardcoded list fails in the worst way: users routed
# through a new range are blocked while everything looks healthy from here.

data "http" "cloudflare_ipv4" {
  url = "https://www.cloudflare.com/ips-v4"

  lifecycle {
    postcondition {
      condition = (
        self.status_code == 200 &&
        length([
          for cidr in split("\n", trimspace(self.response_body)) :
          cidr if trimspace(cidr) != ""
        ]) >= 10
      )
      # This guard is the important part. A failed or truncated fetch would
      # produce an empty list, which generates zero ingress rules, which denies
      # all web traffic. Failing the apply is enormously preferable to
      # silently taking the site off the internet.
      error_message = "Cloudflare published fewer than 10 IPv4 ranges, or the fetch failed. Refusing to apply: an empty list would remove every 80/443 rule and take the origin offline."
    }
  }
}

locals {
  cloudflare_ipv4 = [
    for cidr in split("\n", trimspace(data.http.cloudflare_ipv4.response_body)) :
    trimspace(cidr) if trimspace(cidr) != ""
  ]

  # IPv4 only, deliberately. The origin has no IPv6 address, so Cloudflare
  # always reaches it over IPv4 no matter how the visitor arrived. Adding IPv6
  # rules would require enabling IPv6 on the VCN to protect a path that does
  # not exist.
  http_ingress_cidrs = coalesce(var.http_ingress_cidrs, local.cloudflare_ipv4)
}
