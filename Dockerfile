FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NWAFU_MCP_TRANSPORT=streamable-http \
    NWAFU_MCP_HOST=0.0.0.0 \
    NWAFU_MCP_PORT=8000 \
    NWAFU_MCP_MOUNT_PATH=/mcp

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["mcp-for-nwafactivity"]
