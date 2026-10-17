FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

COPY mcp_server/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY mcp_server ./mcp_server

RUN mkdir -p /app/logs

EXPOSE 8000

CMD ["python", "-m", "mcp_server.server"]