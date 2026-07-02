# OralGuard: AI-Powered Oral Cancer Screening Assistant

OralGuard is an expert clinical screening assistant working under the guidance of **Dr. Urja Sunil Ahuja**. This project is structured as a modular Python application to serve as an interactive triage model for oral cancer screening. 

OralGuard is designed to be highly reliable, running in both **Online Mode** (conversational AI using the Gemini API) and **Offline Mode** (deterministic rule-based triage) to guarantee accessibility in restricted or sandbox environments like Kaggle.

---

## Features
*   💬 **Conversational Online Mode**: Uses Google's modern `google-genai` SDK to carry out a compassionate, adaptive patient interview.
*   🔒 **Robust Offline Fallback**: Automatically switches to a local rules-based workflow if API keys are missing, quota is exceeded, or connection fails.
*   📊 **Streamlit Web Dashboard**: A premium, interactive clinical interface showing conversation logs, dynamic patient dossiers, and real-time risk gauges.
*   💻 **Terminal CLI App**: A lightweight client with ANSI color styling and typewriter animations.
*   🧪 **Automated Testing Suite**: Standardized clinical triage testing covering boundary conditions, missing info checks, and risk levels.

---

## Project Structure
```text
oralguard/
├── triage_engine.py   # Core logic: clinical triage rules & parameter validation
├── agent.py           # Dialogue manager: conversation state, Gemini API, and fallback
├── cli.py             # CLI interface: ANSI coloring, typewriter animations, file exporter
├── app.py             # Streamlit app: web frontend with dynamic patient dossiers
├── test_triage.py     # Automated tests: unit test suite for triage logic
├── requirements.txt   # Project dependencies
└── README.md          # Project guide
```

---

## Clinical Triage Logic & Risk Rules
OralGuard screens patients by collecting:
1. Name and Age
2. Presence and duration of mouth sores, ulcers, or patches
3. History of tobacco, gutka, supari, or pan masala usage (duration & forms)
4. Difficulty swallowing (dysphagia) or difficulty opening the mouth wide (trismus)
5. Pain, burning sensations, or unexplained bleeding

### Risk Classification Matrix:
*   **HIGH RISK**:
    *   Mouth sore, ulcer, or lesion lasting **more than 4 weeks**.
    *   Presence of red (**erythroplakia**) or white (**leukoplakia**) patches.
    *   Tobacco, gutka, or betel nut use for **more than 5 years**.
    *   Difficulty swallowing or difficulty opening the mouth.
    *   Unexplained bleeding or a growing lump in the mouth.
*   **MEDIUM RISK**:
    *   Tobacco/gutka use present but **less than or equal to 5 years**.
    *   Mouth sore/ulcer present for **2 to 4 weeks**.
    *   Unexplained pain or burning sensation in the mouth (without bleeding/lump).
*   **LOW RISK**:
    *   No tobacco use, no patches, no swallowing/mouth-opening issues, no bleeding.
    *   Any mouth sores present have lasted **less than 2 weeks** (or no sores present).

### Insufficient Information Protection:
If a patient skips or fails to provide essential details for any question, the agent raises an `INSUFFICIENT INFORMATION` warning, detailing exactly what parameters are missing, and refuses to classify risk.

---

## Setup & Running Guide

### 1. Installation
Install the required packages:
```bash
pip install -r requirements.txt
```

### 2. Set Up API Key (For Online Mode)
To run in online conversational mode, set your Gemini API key in your environment variables:
*   **Windows (CMD/PowerShell)**:
    ```powershell
    $env:GEMINI_API_KEY="your-api-key-here"
    ```
*   **Linux/macOS**:
    ```bash
    export GEMINI_API_KEY="your-api-key-here"
    ```

### 3. Run the Streamlit Web App
Launch the interactive web portal:
```bash
streamlit run app.py
```

### 4. Run the Terminal CLI
Launch the terminal interview client:
```bash
python cli.py
```

---

## Kaggle Notebook Environment Usage
When submitting to or running in a Kaggle Competition (often offline with no internet access):

```python
# Import the offline triage modules
from triage_engine import assess_risk, validate_inputs

# Sample patient intake data
patient_data = {
    "name": "Alex",
    "age": 42,
    "has_sores": True,
    "sore_type": "ulcer",
    "sore_weeks": 3,
    "has_tobacco": True,
    "tobacco_type": "gutka",
    "tobacco_years": 2,
    "diff_swallowing": False,
    "has_bleeding_q": False
}

# 1. Run Clinical Validation
is_valid, missing_fields = validate_inputs(patient_data)

if not is_valid:
    print(f"Error: Missing fields - {missing_fields}")
else:
    # 2. Run Classification Triage Model
    risk_level, reasons = assess_risk(patient_data)
    print(f"Assessed Risk: {risk_level}")
    print(f"Primary Indicators: {reasons}")
```

### Running Tests in Notebooks:
To verify that the triage engine passes all clinical criteria within your workspace:
```python
!python -m unittest test_triage.py
```
