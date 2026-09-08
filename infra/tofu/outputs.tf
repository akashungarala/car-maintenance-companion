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
  value       = "ssh -i ~/.ssh/cmc_k3s ubuntu@${oci_core_instance.k3s.public_ip}"
}

output "cluster_access_command" {
  description = "Open an SSH tunnel to the Kubernetes API and fetch a kubeconfig for it."
  value       = "scripts/cluster-access.sh"
}

output "app_url" {
  value = "https://${var.app_hostname}"
}

output "api_url" {
  value = "https://${var.api_hostname}"
}
