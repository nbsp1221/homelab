from homelab_infra.hosts import load_hosts

_hosts = load_hosts()
gcp = [name for name, config in _hosts.items() if config["provider"] == "gcp"]
oci = [name for name, config in _hosts.items() if config["provider"] == "oci"]
