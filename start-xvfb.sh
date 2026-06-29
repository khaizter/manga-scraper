# Start a virtual X11 display for headed Chrome in Docker / Cloud Run.
# Source from entrypoint scripts: . /start-xvfb.sh

export DISPLAY=:99

# Clear stale X locks left after abrupt shutdowns (e.g. host reboot).
rm -f /tmp/.X99-lock
rm -rf /tmp/.X11-unix/X99

Xvfb :99 -screen 0 1920x1080x24 -ac -noreset &
XVFB_PID=$!

ready=0
for _ in $(seq 1 30); do
    if xdpyinfo -display :99 >/dev/null 2>&1; then
        ready=1
        break
    fi
    if ! kill -0 "$XVFB_PID" 2>/dev/null; then
        echo "Xvfb exited unexpectedly" >&2
        exit 1
    fi
    sleep 0.5
done

if [ "$ready" -ne 1 ]; then
    echo "Timed out waiting for Xvfb on :99" >&2
    exit 1
fi
