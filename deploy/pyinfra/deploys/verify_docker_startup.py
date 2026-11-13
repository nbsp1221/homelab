from pyinfra import host

from homelab_infra.docker_startup import require_docker_startup
from homelab_infra.hosts import load_hosts

require_docker_startup(load_hosts()[host.name])
