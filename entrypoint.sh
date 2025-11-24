#!/bin/bash
set -e

echo "=========================================="
echo "🚀 Docker Auto-Updater Starting"
echo "=========================================="
echo "Cron schedule: ${CRON_SCHEDULE}"
echo "Label filter: ${AUTOUPDATE_LABEL}"
echo "Auto cleanup: ${AUTO_CLEANUP}"
echo "Force update: ${FORCE_UPDATE}"
echo "Run on startup: ${RUN_ON_STARTUP}"
echo "Timezone: ${TZ}"
echo "=========================================="
echo ""

# Verify Docker connection
if ! docker ps > /dev/null 2>&1; then
    echo "❌ ERROR: Cannot connect to Docker daemon"
    echo "   Make sure /var/run/docker.sock is mounted correctly"
    exit 1
fi

echo "✅ Docker daemon connection successful"
echo ""

# Build the update command based on environment variables
build_update_command() {
    local cmd="python3 /app/autoupdate.py --label \"${AUTOUPDATE_LABEL}\""
    
    if [ "${AUTO_CLEANUP}" = "true" ]; then
        cmd="$cmd --cleanup"
    fi
    
    if [ "${FORCE_UPDATE}" = "true" ]; then
        cmd="$cmd --force"
    fi
    
    echo "$cmd"
}

# Run update function
run_update() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] ========================================" | tee -a /var/log/autoupdate/autoupdate.log
    echo "[$timestamp] Starting update check..." | tee -a /var/log/autoupdate/autoupdate.log
    echo "[$timestamp] ========================================" | tee -a /var/log/autoupdate/autoupdate.log
    
    local cmd=$(build_update_command)
    
    # Execute update and log to file
    eval "$cmd" 2>&1 | tee -a /var/log/autoupdate/autoupdate.log
    
    # Get exit code of the python command (not tee)
    local exit_code=${PIPESTATUS[0]}
    
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    if [ $exit_code -eq 0 ]; then
        echo "[$timestamp] ✅ Update check completed successfully" | tee -a /var/log/autoupdate/autoupdate.log
    else
        echo "[$timestamp] ⚠️  Update check failed with exit code $exit_code" | tee -a /var/log/autoupdate/autoupdate.log
    fi
    echo "" | tee -a /var/log/autoupdate/autoupdate.log
}

# Create log file if it doesn't exist
touch /var/log/autoupdate/autoupdate.log

# Run immediately on startup if enabled
if [ "${RUN_ON_STARTUP}" = "true" ]; then
    echo "🚀 Running initial update (RUN_ON_STARTUP=true)..."
    run_update
fi

# Setup cron job
# Create wrapper script that cron will execute
# This is necessary because cron doesn't have access to functions or complex bash features
cat > /app/run_cron_update.sh << 'CRONSCRIPT'
#!/bin/bash
# Wrapper script for cron execution

# Build command from environment
CMD="python3 /app/autoupdate.py --label \"${AUTOUPDATE_LABEL}\""

if [ "${AUTO_CLEANUP}" = "true" ]; then
    CMD="$CMD --cleanup"
fi

if [ "${FORCE_UPDATE}" = "true" ]; then
    CMD="$CMD --force"
fi

# Log with timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "[$TIMESTAMP] ========================================" >> /var/log/autoupdate/autoupdate.log
echo "[$TIMESTAMP] Cron triggered update check..." >> /var/log/autoupdate/autoupdate.log
echo "[$TIMESTAMP] ========================================" >> /var/log/autoupdate/autoupdate.log

# Execute
eval "$CMD" >> /var/log/autoupdate/autoupdate.log 2>&1

# Log completion
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo "[$TIMESTAMP] ✅ Cron update check completed" >> /var/log/autoupdate/autoupdate.log
else
    echo "[$TIMESTAMP] ⚠️  Cron update check failed with code $EXIT_CODE" >> /var/log/autoupdate/autoupdate.log
fi
echo "" >> /var/log/autoupdate/autoupdate.log
CRONSCRIPT

chmod +x /app/run_cron_update.sh

# Create cron job file
# IMPORTANT: Cron syntax is different - no "root" user needed in container
# Redirect ONLY errors to see if cron itself fails
cat > /etc/cron.d/autoupdate << EOF
# Docker Auto-Updater Cron Job
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
AUTOUPDATE_LABEL=${AUTOUPDATE_LABEL}
AUTO_CLEANUP=${AUTO_CLEANUP}
FORCE_UPDATE=${FORCE_UPDATE}

# Schedule: ${CRON_SCHEDULE}
# Output goes to autoupdate.log, errors printed to stderr
${CRON_SCHEDULE} /app/run_cron_update.sh 2>&1
EOF

# Set correct permissions (cron requires specific permissions)
chmod 0644 /etc/cron.d/autoupdate

# Register the cron job
crontab /etc/cron.d/autoupdate

echo "✅ Cron configured: ${CRON_SCHEDULE}"
echo ""

# Start cron daemon
cron
echo "✅ Cron daemon started"
echo ""
echo "Logs saved to: /var/log/autoupdate/autoupdate.log"
echo "Container running in background. Use 'docker logs -f' to follow updates."
echo ""

# Keep container running by sleeping forever
# Cron runs in background, logs are written to file
exec tail -f /dev/null