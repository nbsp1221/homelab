FROM node:22.23.1-slim

ARG OPENCODEX_VERSION

RUN test -n "${OPENCODEX_VERSION}" \
    && npm install --global --allow-scripts=bun --no-audit --no-fund \
      "@bitkyc08/opencodex@${OPENCODEX_VERSION}" \
    && npm cache clean --force

ENV HOME=/home/node \
    OPENCODEX_HOME=/home/node/.opencodex \
    CODEX_HOME=/home/node/.codex \
    CODEX_HOST_HOME=/run/codex-host

RUN mkdir -p /home/node/.codex \
    && ln -s /run/codex-host/auth.json /home/node/.codex/auth.json \
    && chown -R node:node /home/node/.codex

USER node

EXPOSE 10100

CMD ["ocx", "start", "--port", "10100"]
