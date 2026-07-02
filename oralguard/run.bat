@echo off
echo ==================================================
echo 🦷 OralGuard Setup & Verification Runner
echo ==================================================
echo.

echo 📦 Step 1: Installing/Checking dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo ❌ Dependency installation failed.
    pause
    exit /b %errorlevel%
)
echo.

echo 🧪 Step 2: Running Clinical Triage Unit Tests...
python -m unittest test_triage.py
if %errorlevel% neq 0 (
    echo.
    echo ❌ Unit tests failed.
    pause
    exit /b %errorlevel%
)
echo.
echo ✅ All 14 clinical unit tests passed successfully!
echo.

echo 🚀 Step 3: Starting Streamlit Web Application...
streamlit run app.py
