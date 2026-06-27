#!/bin/bash
# Start the CarLinko dashboard if not already running (cron keep-alive + @reboot).
# Uses ( setsid ... & ) so it fully detaches and survives the launching shell/ssh session.
pgrep -f 'server.py 8088' >/dev/null && exit 0
cd /home/jay/carlinko && ( setsid env PYTHONUNBUFFERED=1 ./venv/bin/python server.py 8088 >> web.log 2>&1 & )
