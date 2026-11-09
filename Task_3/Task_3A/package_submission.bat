@echo off
set /p TEAM_ID="Enter your Team ID (e.g., LQ_1234, or press Enter to skip): "
python "%~dp0package_submission.py" %TEAM_ID%
pause

