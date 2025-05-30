@echo off
REM Script to update a Git repository on Windows

REM --- Configuration ---
set "REPO_DIR=C:\Users\jconn\Tools\Cards\Flipforce"
set "BRANCH_NAME=main"

REM --- Script Logic ---
echo Navigating to repository: %REPO_DIR%
cd /D "%REPO_DIR%"
if errorlevel 1 (
    echo Error: Could not navigate to repository directory: "%REPO_DIR%"
    pause
    exit /b 1
)

echo.
echo Currently in directory:
cd

echo.
echo Currently on branch:
git branch --show-current

echo.
echo Fetching the latest changes from remote for branch '%BRANCH_NAME%'...
git fetch origin "%BRANCH_NAME%"
if errorlevel 1 (
    echo Error: "git fetch" failed.
    pause
    exit /b 1
)

echo.
echo Checking out branch '%BRANCH_NAME%'...
git checkout "%BRANCH_NAME%"
if errorlevel 1 (
    echo Error: Could not checkout branch '%BRANCH_NAME%'.
    pause
    exit /b 1
)

echo.
echo Pulling latest changes for branch '%BRANCH_NAME%'...
git pull origin "%BRANCH_NAME%"
if errorlevel 1 (
    echo Error: "git pull" failed. Resolve conflicts or stash changes first.
    pause
    exit /b 1
)

echo.
echo Update script finished successfully.
pause
