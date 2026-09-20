from pyinfra.operations import apt, server

apt.update(name="Refresh APT package metadata", cache_time=0)
apt.upgrade(name="Upgrade installed packages", auto_remove=False)
server.shell(
    name="Remove unused packages and clean the APT cache",
    commands=(
        "DEBIAN_FRONTEND=noninteractive apt-get autoremove --purge -y && apt-get clean"
    ),
)
server.shell(
    name="Report reboot requirement",
    commands=(
        "if test -e /var/run/reboot-required; then "
        "echo 'Reboot required: yes'; else echo 'Reboot required: no'; fi"
    ),
)
