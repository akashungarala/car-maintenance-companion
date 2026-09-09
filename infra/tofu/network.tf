data "oci_identity_availability_domains" "this" {
  compartment_id = var.tenancy_ocid
}

locals {
  availability_domain = data.oci_identity_availability_domains.this.availability_domains[
    var.availability_domain_index
  ].name
}

resource "oci_core_vcn" "main" {
  compartment_id = var.compartment_ocid
  display_name   = "cmc-vcn"
  cidr_blocks    = ["10.0.0.0/16"]
  dns_label      = "cmc"
}

resource "oci_core_internet_gateway" "main" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.main.id
  display_name   = "cmc-igw"
  enabled        = true
}

resource "oci_core_route_table" "public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.main.id
  display_name   = "cmc-public-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.main.id
  }
}

resource "oci_core_security_list" "public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.main.id
  display_name   = "cmc-public-sl"

  # Outbound is unrestricted: the node pulls images, reaches Let's Encrypt and
  # ships telemetry to Grafana Cloud.
  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }

  # SSH — operator only.
  ingress_security_rules {
    protocol = "6" # TCP
    source   = var.admin_cidr
    tcp_options {
      min = 22
      max = 22
    }
  }

  # The Kubernetes API is deliberately NOT exposed. Argo CD reconciles from
  # inside the cluster (ADR-0008), so nothing external needs 6443, and admin
  # kubectl goes over an SSH tunnel — see scripts/cluster-access.sh.
  #
  # This is not only tighter, it is the only thing that works: k3s issues its
  # API certificate for the node's internal addresses and 127.0.0.1, so
  # connecting to the public IP fails certificate verification anyway. The
  # hostnames are Cloudflare-proxied and Cloudflare does not forward 6443.

  dynamic "ingress_security_rules" {
    for_each = toset(local.http_ingress_cidrs)
    content {
      protocol = "6"
      source   = ingress_security_rules.value
      tcp_options {
        min = 80
        max = 80
      }
    }
  }

  dynamic "ingress_security_rules" {
    for_each = toset(local.http_ingress_cidrs)
    content {
      protocol = "6"
      source   = ingress_security_rules.value
      tcp_options {
        min = 443
        max = 443
      }
    }
  }

  # Path MTU discovery. Without this, large responses hang rather than fail
  # cleanly — a genuinely unpleasant thing to debug.
  ingress_security_rules {
    protocol = "1" # ICMP
    source   = "0.0.0.0/0"
    icmp_options {
      type = 3
      code = 4
    }
  }
}

resource "oci_core_subnet" "public" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.main.id
  display_name               = "cmc-public-subnet"
  cidr_block                 = "10.0.1.0/24"
  route_table_id             = oci_core_route_table.public.id
  security_list_ids          = [oci_core_security_list.public.id]
  dns_label                  = "public"
  prohibit_public_ip_on_vnic = false
}
