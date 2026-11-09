@echo off
set /p TEAM_ID="Enter your Team ID (e.g. 6789 or 89): "
python "%~dp0Task_3\Task_3A\package_submission.py" %TEAM_ID%
pause

