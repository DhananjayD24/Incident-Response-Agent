# syntax=docker/dockerfile:1
# ─────────────────────────────────────────────────────────────────────────────
# Traffic generator — runs Locust in headless mode against order-service.
# Web UI is exposed on :8089 for live stats.
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

WORKDIR /traffic

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY locustfile.py .

# Defaults: 10 users, spawn 2/s, run forever
ENV LOCUST_USERS=10
ENV LOCUST_SPAWN_RATE=2
ENV LOCUST_HOST=http://app:8000
# true  → headless: traffic starts immediately, no web UI (default)
# false → web UI on :8089, press Start to launch traffic manually
ENV LOCUST_HEADLESS=true

EXPOSE 8089

CMD ["sh", "-c", \
     "if [ \"$LOCUST_HEADLESS\" = \"true\" ]; then MODE=\"--headless\"; else MODE=\"\"; fi; \
      exec locust -f locustfile.py \
      --host $LOCUST_HOST \
      --users $LOCUST_USERS \
      --spawn-rate $LOCUST_SPAWN_RATE \
      --web-port 8089 \
      --web-host 0.0.0.0 \
      $MODE"]
