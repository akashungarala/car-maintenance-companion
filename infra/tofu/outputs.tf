output "public_ip" {
  description = "Public IP of the k3s node. Not the address users hit — Cloudflare proxies that."
  value       = oci_core_instance.k3s.public_ip
}

output "availability_domain" {
  description = "The availability domain capacity was actually obtained in."
  value       = local.availability_domain
}

output "ssh_command" {
  description = "SSH to the node."
  value       = "ssh ubuntu@${oci_core_instance.k3s.public_ip}"
}

output "fetch_kubeconfig_command" {
  description = "Copy the cluster kubeconfig locally, rewriting the server address."
  value = join(" ", [
    "ssh ubuntu@${oci_core_instance.k3s.public_ip}",
    "'sudo cat /etc/rancher/k3s/k3s.yaml'",
    "| sed 's|127.0.0.1|${oci_core_instance.k3s.public_ip}|'",
    "> kubeconfig && chmod 600 kubeconfig"
  ])
}

output "app_url" {
  value = "https://${var.app_hostname}"
}

output "api_url" {
  value = "https://${var.api_hostname}"
}
