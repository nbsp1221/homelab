# syntax=docker/dockerfile:1

FROM node:26-slim AS source
WORKDIR /src
ARG RISUAI_REF=3d3dd1a0efbd32c30797ae3802a4dc080d638123

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates git && \
    rm -rf /var/lib/apt/lists/*

RUN git init . && \
    git remote add origin https://github.com/kwaroran/Risuai.git && \
    git fetch --depth 1 origin "$RISUAI_REF" && \
    git checkout FETCH_HEAD
COPY patches /tmp/patches
RUN sh /tmp/patches/apply-patches.sh

FROM node:26-slim AS deps
WORKDIR /app
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

COPY --from=source /src/package.json .
COPY --from=source /src/pnpm-lock.yaml .

RUN npm install --global pnpm@10.34.1
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --prod --frozen-lockfile

FROM deps AS builder
ENV VITE_RISU_LEGAL_CONFIGURED=TRUE

COPY --from=source /src .
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm build

FROM node:26-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production

COPY --from=deps /app/node_modules /app/node_modules
COPY --from=builder /app/server ./server
COPY --from=builder /app/dist ./dist

EXPOSE 6001

CMD ["node", "server/node/server.cjs"]
