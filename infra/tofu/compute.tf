# Canonical's Ubuntu 24.04 for aarch64. Resolved dynamically so the image is
# current, but filtered tightly so an unrelated image cannot be selected.
data "oci_core_images" "ubuntu_arm" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "24.04"
  shape                    = "VM.Standard.A1.Flex"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

resource "oci_core_instance" "k3s" {
  compartment_id      = var.compartment_ocid
  availability_domain = local.availability_domain
  display_name        = "cmc-k3s"
  shape               = "VM.Standard.A1.Flex"

  shape_config {
    ocpus         = var.instance_ocpus
    memory_in_gbs = var.instance_memory_gbs
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu_arm.images[0].id
    boot_volume_size_in_gbs = var.boot_volume_gbs
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.public.id
    assign_public_ip = true
    hostname_label   = "k3s"
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data = base64encode(templatefile("${path.module}/cloud-init.yaml", {
      k3s_version  = var.k3s_version
      app_hostname = var.app_hostname
      api_hostname = var.api_hostname
    }))
  }

  # The boot volume is the cluster's only persistent storage until backups to
  # R2 exist (F6). Losing it by accident would mean rebuilding from scratch.
  preserve_boot_volume = false

  lifecycle {
    # The image is resolved dynamically, so a newer Ubuntu release would
    # otherwise silently propose destroying and recreating the node.
    ignore_changes = [source_details[0].source_id]
  }
}
