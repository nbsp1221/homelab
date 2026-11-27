from tasks import docker, swap, system

system.configure_system()
swap.configure_swap()
docker.install()
