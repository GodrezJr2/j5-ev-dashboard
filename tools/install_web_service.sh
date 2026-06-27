#!/bin/bash
# Install the dashboard as a systemd service (robust, survives reboot/crash).
set -e
pkill -9 -f 'server.py 8088' 2>/dev/null || true
tmux kill-session -t web 2>/dev/null || true
sed -i 's/\r$//' /home/jay/carlinko-web.service
sudo cp /home/jay/carlinko-web.service /etc/systemd/system/carlinko-web.service
sudo systemctl daemon-reload
sudo systemctl enable --now carlinko-web
# stop the cron keep-alive from fighting systemd (remove run_web.sh lines)
crontab -l 2>/dev/null | grep -v 'run_web.sh' | crontab - || true
sleep 3
echo "=== is-active ==="
systemctl is-active carlinko-web
echo "=== listening ==="
ss -tln | grep 8088 || echo "NOT LISTENING"
echo "=== status ==="
systemctl status carlinko-web --no-pager -l 2>&1 | head -12
