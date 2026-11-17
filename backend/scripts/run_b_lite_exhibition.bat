@echo off
setlocal
if "%~1"=="" (
  echo Usage: run_b_lite_exhibition.bat ^<review-manifest.json^>
  echo REVIEW-ONLY preflight. No database access or publishing.
  exit /b 2
)
pushd "%~dp0.." || exit /b 2
python -m scripts.b_lite_exhibition_once --input "%~1"
set "result=%ERRORLEVEL%"
popd
exit /b %result%
