#!/bin/bash

BASE=~/Documents/Development/Experimental/eSRL/eSRLPlatform

BACKEND_API_URL="${BACKEND_API_URL:-http://127.0.0.1:5140}"
GAME_ENGINE_URL="${GAME_ENGINE_URL:-http://127.0.0.1:8000}"
VIDEO_TTS_MAX_CONCURRENCY="${VIDEO_TTS_MAX_CONCURRENCY:-5}"
VIDEO_RENDER_MAX_CONCURRENCY="${VIDEO_RENDER_MAX_CONCURRENCY:-3}"
VIDEO_FFMPEG_MAX_CONCURRENCY="${VIDEO_FFMPEG_MAX_CONCURRENCY:-3}"

osascript <<EOF
tell application "Terminal"
    activate
    
    -- First tab (new window)
    do script "cd $BASE/game-engine && source venv/bin/activate && uvicorn app:app --host 0.0.0.0 --port 8000"
    
    delay 1
    
    -- Create new tab
    tell application "System Events"
        keystroke "t" using command down
    end tell
    
    delay 1
    
    do script "cd $BASE/esrlBackend && source venv/bin/activate && export GAME_ENGINE_API_URL=$GAME_ENGINE_URL && export VIDEO_TTS_MAX_CONCURRENCY=$VIDEO_TTS_MAX_CONCURRENCY && export VIDEO_RENDER_MAX_CONCURRENCY=$VIDEO_RENDER_MAX_CONCURRENCY && export VIDEO_FFMPEG_MAX_CONCURRENCY=$VIDEO_FFMPEG_MAX_CONCURRENCY && python3 -m uvicorn main:app --host 0.0.0.0 --port 5140 --reload" in front window
    
    delay 1
    
    -- Create another new tab
    tell application "System Events"
        keystroke "t" using command down
    end tell
    
    delay 1
    
    do script "cd $BASE/esrl-app && export NEXT_PUBLIC_API_URI=$BACKEND_API_URL && npm run dev" in front window
    
end tell
EOF
