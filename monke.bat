@echo off
setlocal enabledelayedexpansion

REM Monke Test Runner for Windows
REM Based on monke.sh

REM Set UTF-8 encoding for Python subprocesses
set "PYTHONIOENCODING=utf-8"

REM Configuration
set "SCRIPT_DIR=%~dp0"
set "MONKE_DIR=%SCRIPT_DIR%monke"
set "VENV_DIR=%MONKE_DIR%\venv"
set "LOGS_DIR=%MONKE_DIR%\logs"
set "AIRWEAVE_API_URL=%AIRWEAVE_API_URL%"
if "%AIRWEAVE_API_URL%"=="" set "AIRWEAVE_API_URL=http://localhost:8001"
set "AZURE_KEY_VAULT_URL=%AZURE_KEY_VAULT_URL%"
set "MONKE_MAX_PARALLEL=%MONKE_MAX_PARALLEL%"
if "%MONKE_MAX_PARALLEL%"=="" set "MONKE_MAX_PARALLEL=5"
set "MONKE_ENV_FILE=%MONKE_ENV_FILE%"
if "%MONKE_ENV_FILE%"=="" set "MONKE_ENV_FILE=%MONKE_DIR%\.env"
set "MONKE_MIN_CONNECTORS=%MONKE_MIN_CONNECTORS%"
if "%MONKE_MIN_CONNECTORS%"=="" set "MONKE_MIN_CONNECTORS=4"

REM Parse arguments
set "connectors="
set "mode=specific"
set "print_connectors=false"
set "help=false"
set "list=false"

:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="--help" set "help=true" & shift & goto parse_args
if /i "%~1"=="-h" set "help=true" & shift & goto parse_args
if /i "%~1"=="--list" set "list=true" & shift & goto parse_args
if /i "%~1"=="-l" set "list=true" & shift & goto parse_args
if /i "%~1"=="--print-connectors" set "print_connectors=true" & shift & goto parse_args
if /i "%~1"=="--all" set "mode=all" & shift & goto parse_args
if /i "%~1"=="-a" set "mode=all" & shift & goto parse_args
if /i "%~1"=="--changed" set "mode=changed" & shift & goto parse_args
if /i "%~1"=="-c" set "mode=changed" & shift & goto parse_args
if /i "%~1"=="--verbose" set "MONKE_VERBOSE=1" & shift & goto parse_args
if /i "%~1"=="-v" set "MONKE_VERBOSE=1" & shift & goto parse_args
REM Check if argument starts with -- (unknown option)
set "arg=%~1"
if "!arg:~0,2!"=="--" (
    echo ERROR: Unknown option: %~1
    goto show_usage
)
set "connectors=!connectors! %~1"
shift
goto parse_args

:args_done

REM Show help
if "%help%"=="true" goto show_usage
if "%list%"=="true" goto list_connectors

REM Check if CI
set "CI_MODE=false"
if not "%CI%"=="" set "CI_MODE=true"
if not "%GITHUB_ACTIONS%"=="" set "CI_MODE=true"

echo.
echo 🐒 Monke Test Runner
echo.

REM Setup virtual environment
call :setup_venv
if errorlevel 1 exit /b 1

REM Check backend (skip in CI)
if "%CI_MODE%"=="false" (
    call :check_backend
    if errorlevel 1 exit /b 1
)

REM Determine connectors based on mode
if "%print_connectors%"=="true" (
    call :get_connectors_for_mode "%mode%" connectors_list
    echo %connectors_list%
    exit /b 0
)

call :get_connectors_for_mode "%mode%" connectors_list
if errorlevel 1 exit /b 1

REM Run tests
call :run_tests %connectors_list%
set "test_exit=%errorlevel%"

if %test_exit% equ 0 (
    echo.
    echo ✅ All tests passed! 🎉
    exit /b 0
) else (
    echo.
    echo ❌ Some tests failed. Check logs in %LOGS_DIR%\
    exit /b 1
)

REM ============================================
REM Functions
REM ============================================

:show_usage
echo.
echo 🐒 Monke Test Runner
echo.
echo Usage:
echo     monke.bat [connector...]           Run specific connector^(s^)
echo     monke.bat --changed                Run core connectors + any changed connectors
echo     monke.bat --all                    Run all connectors in parallel
echo     monke.bat --list                   List available connectors
echo     monke.bat --print-connectors       Print connectors that would be tested
echo     monke.bat --help                   Show this help
echo.
echo Examples:
echo     monke.bat github                   Run GitHub connector test
echo     monke.bat github asana notion      Run multiple specific connectors
echo     monke.bat --changed                Run core + changed connectors
echo     monke.bat --all                    Run all connector tests in parallel
echo.
echo Environment:
echo     AIRWEAVE_API_URL                   Backend URL (default: http://localhost:8001^)
echo     AZURE_KEY_VAULT_URL                Azure Key Vault URL (optional^)
echo     MONKE_MAX_PARALLEL                 Max parallel tests (default: 5^)
echo     MONKE_ENV_FILE                     Environment file (default: monke/.env^)
echo     MONKE_NO_VENV                      Skip venv setup (if set^)
echo     MONKE_VERBOSE                      Verbose output (if set^)
echo.
exit /b 0

:setup_venv
if not "%MONKE_NO_VENV%"=="" if "%MONKE_NO_VENV%"=="1" (
    echo ℹ  Skipping venv setup (MONKE_NO_VENV=1)
    goto :eof
)

if "%CI_MODE%"=="true" (
    echo ℹ  CI environment detected, skipping venv setup
    goto :eof
)

if not exist "%VENV_DIR%" (
    echo ▶  Creating Python virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo ❌ Failed to create virtual environment
        exit /b 1
    )
    echo ✅ Virtual environment created
)

echo ▶  Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo ❌ Failed to activate virtual environment
    exit /b 1
)

REM Check if airweave is installed
python -c "import airweave" 2>nul
if errorlevel 1 (
    echo ▶  Installing dependencies...
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet -r "%MONKE_DIR%\requirements.txt"
    if errorlevel 1 (
        echo ❌ Failed to install dependencies
        exit /b 1
    )

    REM Install Azure dependencies if Key Vault is configured
    if not "%AZURE_KEY_VAULT_URL%"=="" (
        echo ▶  Installing Azure Key Vault dependencies...
        python -m pip install --quiet azure-keyvault-secrets azure-identity
    )

    echo ✅ Dependencies installed
) else (
    echo ℹ  Dependencies already installed

    REM Check Azure dependencies if Key Vault is configured
    if not "%AZURE_KEY_VAULT_URL%"=="" (
        python -c "import azure.keyvault.secrets" 2>nul
        if errorlevel 1 (
            echo ▶  Installing Azure Key Vault dependencies...
            python -m pip install --quiet azure-keyvault-secrets azure-identity
        )
    )
)
goto :eof

:list_connectors
echo Available connectors:
for %%f in ("%MONKE_DIR%\configs\*.yaml") do (
    set "filename=%%~nf"
    echo   • !filename!
)
exit /b 0

:get_available_connectors
setlocal enabledelayedexpansion
set "connectors_list="
for %%f in ("%MONKE_DIR%\configs\*.yaml") do (
    set "filename=%%~nf"
    set "connectors_list=!connectors_list! !filename!"
)
endlocal & set "connectors_list=%connectors_list%"
goto :eof

:get_core_connectors
setlocal enabledelayedexpansion
set "core_connectors=github asana linear google_docs word"
set "connectors_list="
for %%c in (%core_connectors%) do (
    if exist "%MONKE_DIR%\configs\%%c.yaml" (
        set "connectors_list=!connectors_list! %%c"
    )
)
endlocal & set "connectors_list=%connectors_list%"
goto :eof

:detect_changed_connectors
setlocal enabledelayedexpansion
set "base_branch=%BASE_BRANCH%"
if "%base_branch%"=="" set "base_branch=main"

echo ▶  Detecting changed connectors vs %base_branch%...

REM Check if git is available
git --version >nul 2>&1
if errorlevel 1 (
    echo ⚠  Cannot detect changes (git not found)
    exit /b 1
)

REM Get changed files
set "changed_connectors="
for /f "delims=" %%f in ('git diff --name-only %base_branch%...HEAD 2^>nul ^| findstr /R "monke\\bongos\\ monke\\configs\\ monke\\generation\\ backend\\airweave\\platform\\sources\\ backend\\airweave\\platform\\entities\\"') do (
    set "file=%%f"
    
    REM Extract connector name from path
    set "connector="
    echo !file! | findstr /R "monke\\bongos\\" >nul
    if not errorlevel 1 (
        for /f "tokens=3 delims=\" %%a in ("!file!") do (
            set "connector=%%~na"
        )
    ) else (
        echo !file! | findstr /R "monke\\configs\\" >nul
        if not errorlevel 1 (
            for /f "tokens=3 delims=\" %%a in ("!file!") do (
                set "connector=%%~na"
            )
        ) else (
            echo !file! | findstr /R "monke\\generation\\" >nul
            if not errorlevel 1 (
                for /f "tokens=3 delims=\" %%a in ("!file!") do (
                    set "connector=%%~na"
                )
            ) else (
                echo !file! | findstr /R "backend\\airweave\\platform\\sources\\" >nul
                if not errorlevel 1 (
                    for /f "tokens=5 delims=\" %%a in ("!file!") do (
                        set "connector=%%~na"
                    )
                ) else (
                    echo !file! | findstr /R "backend\\airweave\\platform\\entities\\" >nul
                    if not errorlevel 1 (
                        for /f "tokens=5 delims=\" %%a in ("!file!") do (
                            set "connector=%%~na"
                        )
                    )
                )
            )
        )
    )
    
    REM Check if connector config exists and add to list
    if not "!connector!"=="" (
        if exist "%MONKE_DIR%\configs\!connector!.yaml" (
            echo !changed_connectors! | findstr /C:" !connector! " >nul
            if errorlevel 1 (
                set "changed_connectors=!changed_connectors! !connector!"
            )
        )
    )
)

if "!changed_connectors!"=="" (
    echo ℹ  No testable connector changes detected
    exit /b 1
)

echo ✅ Detected changed connectors:!changed_connectors!
endlocal & set "changed_connectors=%changed_connectors%"
goto :eof

:get_hybrid_connectors
setlocal enabledelayedexpansion
call :get_core_connectors
set "all_connectors=%connectors_list%"

call :detect_changed_connectors
if not errorlevel 1 (
    REM Add changed connectors that aren't already in core
    for %%c in (%changed_connectors%) do (
        echo %all_connectors% | findstr /C:" %%c " >nul
        if errorlevel 1 (
            set "all_connectors=!all_connectors! %%c"
        )
    )
)

endlocal & set "connectors_list=%all_connectors%"
goto :eof

:ensure_min_connectors
setlocal enabledelayedexpansion
set "input_connectors=%~1"
set "connector_count=0"
for %%c in (%input_connectors%) do set /a connector_count+=1

if %connector_count% geq %MONKE_MIN_CONNECTORS% (
    endlocal & set "connectors_list=%input_connectors%"
    goto :eof
)

echo ℹ  Only %connector_count% connectors, padding to minimum of %MONKE_MIN_CONNECTORS%...
call :get_available_connectors
set "available=%connectors_list%"
set "result=%input_connectors%"

for %%c in (%available%) do (
    if %connector_count% geq %MONKE_MIN_CONNECTORS% goto min_done
    echo %input_connectors% | findstr /C:" %%c " >nul
    if errorlevel 1 (
        set "result=!result! %%c"
        set /a connector_count+=1
        echo ℹ  Added extra connector: %%c
    )
)

:min_done
endlocal & set "connectors_list=%result%"
goto :eof

:check_backend
echo ▶  Checking Airweave backend at %AIRWEAVE_API_URL%...
curl -fsS "%AIRWEAVE_API_URL%/health" >nul 2>&1
if errorlevel 1 (
    echo ❌ Backend is not accessible at %AIRWEAVE_API_URL%
    echo ℹ  Please ensure Airweave is running (./start.sh or docker-compose up^)
    exit /b 1
)
echo ✅ Backend is healthy
goto :eof

:get_connectors_for_mode
setlocal enabledelayedexpansion
set "mode=%~1"
set "result="

if "%mode%"=="all" (
    call :get_available_connectors
    set "result=%connectors_list%"
) else if "%mode%"=="changed" (
    call :get_hybrid_connectors
    set "result=%connectors_list%"
    if "!result!"=="" (
        echo ❌ No connectors available for testing
        exit /b 1
    )
) else (
    REM specific mode
    if not "%connectors%"=="" (
        set "result=%connectors%"
    ) else (
        call :get_hybrid_connectors
        set "result=%connectors_list%"
        if "!result!"=="" (
            echo ❌ No connectors available for testing
            exit /b 1
        )
    )
)

REM Ensure minimum connectors for CI
if "%print_connectors%"=="true" (
    call :ensure_min_connectors "%result%"
    set "result=%connectors_list%"
)

endlocal & set "connectors_list=%result%"
goto :eof

:run_tests
setlocal enabledelayedexpansion
set "connectors_list=%~1"
if "%connectors_list%"=="" (
    echo ❌ No connectors to test
    exit /b 1
)

REM Check environment file
if not exist "%MONKE_ENV_FILE%" (
    echo ❌ Environment file not found: %MONKE_ENV_FILE%
    echo ℹ  Create monke/.env and add your credentials (or set MONKE_ENV_FILE^)
    exit /b 1
)

REM Create logs directory
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"
REM Get timestamp using PowerShell (wmic is deprecated in Windows 11+)
for /f "delims=" %%a in ('powershell -Command "Get-Date -Format 'yyyyMMdd_HHmmss'"') do set "timestamp=%%a"

REM Validate connector configs exist
set "valid_connectors="
for %%c in (%connectors_list%) do (
    if exist "%MONKE_DIR%\configs\%%c.yaml" (
        set "valid_connectors=!valid_connectors! %%c"
    ) else (
        echo ❌ Config not found for connector: %%c
        exit /b 1
    )
)

echo ▶  Running connector test(s^) in parallel (max %MONKE_MAX_PARALLEL%^)...
echo Connectors:%valid_connectors%
echo.

REM Change to monke directory
pushd "%MONKE_DIR%"

REM Get just the filename for env file
for %%f in ("%MONKE_ENV_FILE%") do set "env_filename=%%~nxf"

REM Run the unified runner
python runner.py %valid_connectors% --env "%env_filename%" --max-concurrency %MONKE_MAX_PARALLEL% --run-id-prefix "local-"
set "exit_code=%errorlevel%"

REM Save latest log reference
if exist "%LOGS_DIR%" (
    echo %timestamp% > "%LOGS_DIR%\.latest"
)

popd
endlocal & exit /b %exit_code%



