from homelab_infra.docker import configure_docker
from homelab_infra.swap import configure_swap
from homelab_infra.system import configure_system

configure_system()
configure_swap()
configure_docker()
