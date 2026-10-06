# CodeScan MCP server, packaged for `docker run -i` (stdio transport).
# The scanner talks to Neo4j over the network, so no database runs in this
# image -- point NEO4J_HOST/NEO4J_PORT_BOLT/NEO4J_USER/NEO4J_PASSWORD (see
# example.env) at a reachable instance, e.g. the one docker-compose.yaml starts.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Dependencies first, so source edits keep this layer cached
COPY pyproject.toml uv.lock version.txt README.md ./
RUN uv sync --locked --no-dev --no-install-project

# Run as an unprivileged user -- an MCP tool executes arbitrary scan logic
# against whatever the client points it at, so it shouldn't run as root.
RUN useradd --create-home --shell /usr/sbin/nologin codescan \
    && chown codescan:codescan /app
COPY --chown=codescan:codescan . .
RUN uv sync --locked --no-dev
USER codescan

ENTRYPOINT ["/app/.venv/bin/codescan-mcp"]
