@echo off
REM Script to commit and push local changes to a Git repository on Windows

REM --- Configuration ---
set "REPO_DIR=C:\Users\jconn\Tools\Cards\Flipforce"
set "BRANCH_NAME=main"
set "COMMIT_MSG=Auto-commit: Updated via script"

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
echo Checking current branch...
git checkout "%BRANCH_NAME%"
if errorlevel 1 (
    echo Error: Could not checkout branch '%BRANCH_NAME%'.
    pause
    exit /b 1
)

echo.
echo Pulling latest changes from remote...
git pull origin "%BRANCH_NAME%"
if errorlevel 1 (
    echo Error: "git pull" failed.
    pause
    exit /b 1
)

echo.
echo Adding all changes...
git add .
if errorlevel 1 (
    echo Error: "git add" failed.
    pause
    exit /b 1
)

echo.
echo Committing changes...
git commit -m "%COMMIT_MSG%"
if errorlevel 1 (
    echo No changes to commit or commit failed.
    goto PUSH
)

:PUSH
echo.
echo Pushing changes to origin/%BRANCH_NAME%...
git push origin "%BRANCH_NAME%"
if errorlevel 1 (
    echo Error: "git push" failed.
    pause
    exit /b 1
)

echo.
echo ✅ Repository updated successfully.
pause
