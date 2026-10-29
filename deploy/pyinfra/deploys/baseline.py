from homelab_infra.dns import configure_dns
from homelab_infra.docker import configure_docker
from homelab_infra.docker_startup import configure_docker_startup
from homelab_infra.swap import configure_swap
from homelab_infra.system import configure_system

configure_system()
configure_dns()
configure_swap()
configure_docker_startup()
configure_docker()
