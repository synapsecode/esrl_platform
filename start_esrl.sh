#!/bin/bash

BASE=~/Documents/Development/Experimental/eSRL/eSRLPlatform

osascript <<EOF
tell application "Terminal"
    activate

    do script "cd $BASE/game-engine && source venv/bin/activate && uvicorn app:app --host 0.0.0.0 --port 8000"
    delay 1
    do script "cd $BASE/esrlBackend && source venv/bin/activate && python -m uvicorn main:app --host 0.0.0.0 --port 5140 --reload" in front window
    delay 1
    do script "cd $BASE/esrl-app && npm run dev" in front window
end tell
EOF