# code-server

Legacy development image with a local workspace bind mount.

Before starting, create an ignored `.env` file and set a unique password:

```bash
cp .env.example .env
chmod 600 .env
openssl rand -hex 32
```

Put the generated value in `CODE_SERVER_PASSWORD`; do not commit `.env`.
Compose passes it through the official `PASSWORD` environment variable.
The image configuration keeps password authentication enabled and contains
no fixed password. Compose refuses to start when the password is empty.

```bash
docker compose config -q
docker compose up -d --build
```
