#!/bin/bash
set -e

# Check config files
if [ ! -f "/app/config/config.yaml" ] || [ ! -f "/app/config/frequency_words.txt" ]; then
    echo "❌ Config files missing"
    exit 1
fi

# Save environment variables
env >> /etc/environment

case "${RUN_MODE:-cron}" in
"once")
    echo "🔄 Single execution"
    exec /usr/local/bin/python main.py
    ;;
"cron")
    # Generate crontab
    echo "${CRON_SCHEDULE:-*/30 * * * *} cd /app && /usr/local/bin/python main.py" > /tmp/crontab

    echo "📅 Generated crontab content:"
    cat /tmp/crontab

    if ! /usr/local/bin/supercronic -test /tmp/crontab; then
        echo "❌ Crontab format validation failed"
        exit 1
    fi

    # Execute immediately if configured
    if [ "${IMMEDIATE_RUN:-false}" = "true" ]; then
        echo "▶️ Executing immediately"
        /usr/local/bin/python main.py
    fi

    echo "⏰ Starting supercronic: ${CRON_SCHEDULE:-*/30 * * * *}"
    echo "🎯 supercronic will run as PID 1"

    exec /usr/local/bin/supercronic -passthrough-logs /tmp/crontab
    ;;
*)
    exec "$@"
    ;;
esac
