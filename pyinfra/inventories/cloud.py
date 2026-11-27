_gcp_ingress = "retn0-srv-gcp-01"
gcp = [_gcp_ingress]
gcp_ingress = ([_gcp_ingress], {"stacks": {"caddy-gcp": {}}})
oci = ["retn0-srv-oci-01", "retn0-srv-oci-02"]
