#!/bin/bash
# Set up + run Blutter (Dart AOT decompiler) on libapp.so to recover the request-signing
# function. Long-running; logs to ~/blutter/run.log.
mkdir -p ~/blutter_work
exec >> ~/blutter_work/run.log 2>&1
echo "===== start $(date) ====="
set -x
sudo apt-get update -y
sudo apt-get install -y cmake ninja-build pkg-config libicu-dev build-essential
cd ~
if [ ! -d blutter ]; then git clone https://github.com/worawit/blutter.git; fi
cd blutter
pip3 install --break-system-packages requests pyelftools 2>/dev/null || pip3 install requests pyelftools
python3 blutter.py ~/blutter_in ~/blutter_work/out_carlinko
echo "===== done $(date) rc=$? ====="
