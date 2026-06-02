@echo off
cd /d "d:\project\agent"
echo [%date% %time%] Starting Daily UPSC Agent Run >> agent_runs.log
python main.py >> agent_runs.log 2>&1
echo [%date% %time%] Daily UPSC Agent Run Completed >> agent_runs.log
