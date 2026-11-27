from pyinfra import host

from tasks import docker, swap, system

if "cloud" in host.groups:
    system.configure_system()
    swap.configure_swap()
    docker.install()
