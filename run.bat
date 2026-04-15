@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

set "SCRIPT=%~dp0ff.py"
set "PY=%~dp0python-3.13.13-embed-amd64\python.exe"
if not exist "%PY%" set "PY=%USERPROFILE%\Desktop\python-3.13.13-embed-amd64\python.exe"

if not exist "%SCRIPT%" (
  echo [ERROR] ff.py not found: %SCRIPT%
  pause
  exit /b 1
)

if not exist "%PY%" (
  echo [ERROR] python.exe not found:
  echo %PY%
  echo Please edit the PY path in run.bat.
  pause
  exit /b 1
)

:menu
cls
echo =======================================
echo  File Index Tool
echo =======================================
echo 1. Scan one folder
echo 2. Search by keyword
echo 3. Search by category
echo 4. Search by extension
echo 5. Show stats
echo 6. Clean missing records
echo 7. Scan all local drives (C/D/E...)
echo 0. Exit
echo =======================================
set /p choice=Select: 

if "%choice%"=="1" goto scan_one
if "%choice%"=="2" goto search_kw
if "%choice%"=="3" goto search_cat
if "%choice%"=="4" goto search_ext
if "%choice%"=="5" goto stats
if "%choice%"=="6" goto clean
if "%choice%"=="7" goto scan_all
if "%choice%"=="0" exit /b 0
goto menu

:scan_one
set "dir="
set /p dir=Folder path: 
if "%dir%"=="" goto menu
"%PY%" "%SCRIPT%" scan "%dir%"
pause
goto menu

:search_kw
set "kw="
set /p kw=Keyword: 
if "%kw%"=="" goto menu
"%PY%" "%SCRIPT%" search "%kw%" -l 50
pause
goto menu

:search_cat
set "cat="
set /p cat=Category (文档/图片/视频/音频/压缩包/代码/可执行/CAD图纸/Unity工程/其他): 
if "%cat%"=="" goto menu
"%PY%" "%SCRIPT%" search -c "%cat%" -l 50
pause
goto menu

:search_ext
set "ext="
set /p ext=Extension (e.g. pdf/jpg/py): 
if "%ext%"=="" goto menu
"%PY%" "%SCRIPT%" search -e "%ext%" -l 50
pause
goto menu

:stats
"%PY%" "%SCRIPT%" stats
pause
goto menu

:clean
"%PY%" "%SCRIPT%" clean
pause
goto menu

:scan_all
echo Scanning all local drives. This may take a long time...
set "found=0"
for /f "skip=1 tokens=1" %%D in ('wmic logicaldisk where "DriveType=3" get DeviceID 2^>nul') do (
  if not "%%D"=="" (
    set "found=1"
    echo [SCAN] %%D\
    "%PY%" "%SCRIPT%" scan "%%D\"
  )
)

if "!found!"=="0" (
  echo WMIC not available, fallback by drive letters...
  for %%L in (C D E F G H I J K L M N O P Q R S T U V W X Y Z) do (
    if exist "%%L:\" (
      echo [SCAN] %%L:\
      "%PY%" "%SCRIPT%" scan "%%L:\"
    )
  )
)

echo Done.
pause
goto menu
