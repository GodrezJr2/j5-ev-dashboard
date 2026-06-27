#!/bin/bash
# Stop the dense drive-capture poller and revert logger cron to every 15 min.
sudo systemctl stop carlinko-dense 2>/dev/null || true
sudo systemctl reset-failed carlinko-dense 2>/dev/null || true
pkill -f 'logger.py --loop' 2>/dev/null || true
crontab -l 2>/dev/null | sed 's#^\*/1 \* \* \* \* cd#*/15 * * * * cd#' | crontab -
echo "CRON:"; crontab -l | grep 'logger.py'
echo "DENSE:"; systemctl is-active carlinko-dense 2>/dev/null || echo stopped
