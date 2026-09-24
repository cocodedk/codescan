# CodeScan MCP server, packaged for `docker run -i` (stdio transport).
# The scanner talks to Neo4j over the network, so no database runs in this
# image -- point NEO4J_HOST/NEO4J_PORT_BOLT/NEO4J_USER/NEO4J_PASSWORD (see
# example.env) at a reachable instance, e.g. the one docker-compose.yaml starts.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as an unprivileged user -- an MCP tool executes arbitrary scan logic
# against whatever the client points it at, so it shouldn't run as root.
RUN useradd --create-home --shell /usr/sbin/nologin codescan \
    && chown -R codescan:codescan /app
USER codescan

ENTRYPOINT ["python", "codescan_mcp_server.py"]
