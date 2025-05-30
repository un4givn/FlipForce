@echo off
echo DEBUG: Script started.
pause

REM Batch file to add, commit, and push changes to GitHub

REM Ensure Git is available
git --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Git is not found. Please ensure Git is installed and in your PATH.
    pause
    exit /b 1
)
echo DEBUG: Git is found.
pause

REM Navigate to the script's directory (where the .git folder should be)
REM This makes the script runnable from anywhere if it's placed in the project root
cd /D "%~dp0"
echo DEBUG: Changed directory to %cd%
pause

echo =======================================================
echo          UPDATING GITHUB REPOSITORY
echo =======================================================
echo.

REM Check for uncommitted changes
echo DEBUG: Checking for uncommitted changes...
git status --porcelain > git_status.tmp
echo DEBUG: git status --porcelain completed. Errorlevel: %ERRORLEVEL%
pause

set "CHANGES_EXIST="
REM The FOR loop will only set CHANGES_EXIST if git_status.tmp is not empty
FOR /F "usebackq tokens=*" %%A IN (`type git_status.tmp`) DO SET CHANGES_EXIST=TRUE
del git_status.tmp

IF NOT DEFINED CHANGES_EXIST (
    echo DEBUG: No changes detected block.
    echo No changes to commit. Working tree clean.
    git status
    echo.
    echo Pulling latest changes from remote...
    pause
    git pull origin main
    echo DEBUG: git pull completed. Errorlevel: %ERRORLEVEL%
    pause
    goto end
)

echo DEBUG: Changes detected block.
pause

echo Staging all changes...
git add .
echo DEBUG: git add . completed. Errorlevel: %ERRORLEVEL%
pause
echo.

echo Checking status after adding files:
git status
echo.

REM Prompt for a commit message
set /p COMMIT_MESSAGE="Enter your commit message: "

IF "%COMMIT_MESSAGE%"=="" (
    echo Commit message cannot be empty. Aborting.
    goto end
)

echo.
echo Committing changes with message: "%COMMIT_MESSAGE%"
git commit -m "%COMMIT_MESSAGE%"
echo DEBUG: git commit completed. Errorlevel: %ERRORLEVEL%
pause
echo.

echo Pushing changes to origin main...
git push origin main
echo DEBUG: git push completed. Errorlevel: %ERRORLEVEL%
pause

IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo *******************************************************
    echo * GIT PUSH FAILED. Please check for errors above.  *
    echo * You might need to 'git pull' first if there are  *
    echo * remote changes, or resolve authentication issues.*
    echo *******************************************************
) ELSE (
    echo.
    echo =======================================================
    echo      Successfully pushed to GitHub!
    echo =======================================================
)

:end
echo.
echo Press any key to close this window.
pause >nul
