@echo off
rem Re-downloads setlist.fm, recomputes, updates the two Spotify playlists and regenerates the report.
rem Run it by hand (double click or from a terminal). Log in logs\update.log.
rem If a step fails, it stops before touching Spotify.
cd /d "%~dp0"
if not exist logs mkdir logs
set PYTHONIOENCODING=utf-8
set LOG=logs\update.log
echo ===== %date% %time% ===== >> %LOG%
python build_db.py --refresh >> %LOG% 2>&1 || goto :error
python analyze.py >> %LOG% 2>&1 || goto :error
python spotify.py links >> %LOG% 2>&1 || goto :error
python analyze.py >> %LOG% 2>&1 || goto :error
python spotify.py create >> %LOG% 2>&1 || goto :error
python report.py >> %LOG% 2>&1 || goto :error
echo OK >> %LOG%
exit /b 0
:error
echo FAILED: check the previous step >> %LOG%
exit /b 1
