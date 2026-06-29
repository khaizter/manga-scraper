FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CHROME_BIN=/usr/bin/google-chrome \
    CHROME_HEADLESS=false

WORKDIR /app

ARG TARGETARCH

# xvfb/xauth: virtual display for Chrome (headless is blocked by the target site)
# curl: healthcheck | wget: download Chrome on amd64
# arm64: Google Chrome .deb is amd64-only today; use distro Chromium instead
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    tini \
    wget \
    x11-utils \
    xvfb \
    xauth \
    && if [ "${TARGETARCH}" = "amd64" ]; then \
         wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
         && apt-get install -y --no-install-recommends /tmp/google-chrome.deb \
         && rm /tmp/google-chrome.deb; \
       elif [ "${TARGETARCH}" = "arm64" ]; then \
         apt-get install -y --no-install-recommends chromium \
         && ln -sf /usr/bin/chromium /usr/bin/google-chrome; \
       else \
         echo "Unsupported TARGETARCH: ${TARGETARCH}" >&2; exit 1; \
       fi \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY cli.py .
COPY credentials/brightdata/ /app/credentials/brightdata/
COPY start-xvfb.sh /start-xvfb.sh
COPY entrypoint.sh /entrypoint.sh
COPY job-entrypoint.sh /job-entrypoint.sh
RUN sed -i 's/\r$//' /start-xvfb.sh /entrypoint.sh /job-entrypoint.sh \
    && chmod +x /start-xvfb.sh /entrypoint.sh /job-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
