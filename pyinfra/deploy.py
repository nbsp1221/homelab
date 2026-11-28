from pyinfra import host

from tasks import docker, swap

if "cloud" in host.groups:
    swap.configure_swap()
    docker.install()
