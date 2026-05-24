FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CHROME_BIN=/usr/bin/google-chrome \
    CHROME_HEADLESS=false

WORKDIR /app

# xvfb/xauth: virtual display for Chrome (headless is blocked by the target site)
# curl: healthcheck | wget: download Chrome | Chrome .deb pulls its own lib deps via apt
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    wget \
    xvfb \
    xauth \
    && wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y --no-install-recommends /tmp/google-chrome.deb \
    && rm /tmp/google-chrome.deb \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY cli.py .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

CMD ["xvfb-run", "-a", "--server-args=-screen 0 1920x1080x24", \
     "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
