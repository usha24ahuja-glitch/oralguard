import os
import re
import time
import sys
from google import genai
from google.genai import types
from google.genai import errors

# Enable Virtual Terminal Processing on Windows to support ANSI color sequences
try:
    if os.name == 'nt':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
except Exception:
    pass

# ANSI Color Codes for terminal formatting
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_CYAN = "\033[1;36m"
COLOR_GREEN = "\033[1;32m"
COLOR_YELLOW = "\033[1;33m"
COLOR_RED = "\033[1;31m"
COLOR_MAGENTA = "\033[1;35m"
COLOR_WHITE = "\033[1;37m"

# Typewriter typing animation helper
def typewriter_print(text, delay=0.008):
    i = 0
    while i < len(text):
        if text[i] == "\033":
            # Print complete ANSI escape sequence at once so it doesn't flash raw characters
            end = text.find("m", i)
            if end != -1:
                sys.stdout.write(text[i:end+1])
                i = end + 1
                continue
        sys.stdout.write(text[i])
        sys.stdout.flush()
        time.sleep(delay)
        i += 1
    print()

# Beautiful report summarizing helper
def build_report_summary(name, age, has_sores, sore_type, sore_weeks, has_tobacco, tobacco_type, tobacco_years, diff_swallowing, swallow_detail, swallow_duration, has_bleeding, bleeding_detail, risk, reasons):
    risk_display = risk
    if risk == "HIGH RISK":
        risk_display = f"{COLOR_BOLD}{COLOR_RED}HIGH RISK{COLOR_RESET}"
        advice = (f"\n🏥 {COLOR_BOLD}Dr. Urja's Recommended Next Steps:{COLOR_RESET}\n"
                  "I strongly advise you to schedule a visit to an oral surgeon or specialist "
                  "within the next week for a professional checkup and clinical evaluation. Please don't worry, but taking "
                  "early action is the best path to stay safe.")
    elif risk == "MEDIUM RISK":
        risk_display = f"{COLOR_BOLD}{COLOR_YELLOW}MEDIUM RISK{COLOR_RESET}"
        advice = (f"\n🏥 {COLOR_BOLD}Dr. Urja's Recommended Next Steps:{COLOR_RESET}\n"
                  "I suggest visiting your dentist within the next 2 to 4 weeks for a detailed checkup and evaluation "
                  "to monitor these symptoms and ensure everything heals correctly.")
    else:
        risk_display = f"{COLOR_BOLD}{COLOR_GREEN}LOW RISK{COLOR_RESET}"
        advice = (f"\n🏥 {COLOR_BOLD}Dr. Urja's Recommended Next Steps:{COLOR_RESET}\n"
                  "I suggest maintaining standard, healthy oral hygiene habits and scheduling regular dental checkups "
                  "every 6 months. This helps keep your mouth healthy and prevents future issues!")

    reasons_desc = ", ".join(reasons) if reasons else "No abnormal factors identified"

    report = f"""
==================================================
📋  {COLOR_BOLD}PATIENT SCREENING REPORT SUMMARY{COLOR_RESET}
==================================================
👤 {COLOR_BOLD}Patient Name & Age:{COLOR_RESET}  {name}, {age} years
🩹 {COLOR_BOLD}Mouth Sores/Ulcers:{COLOR_RESET}  {"Yes - " + sore_type + " (" + str(sore_weeks) + " weeks)" if has_sores else "None"}
🚬 {COLOR_BOLD}Tobacco/Gutka Use:{COLOR_RESET}   {"Yes - " + tobacco_type + " (" + str(tobacco_years) + " years)" if has_tobacco else "None"}
👅 {COLOR_BOLD}Difficulty opening:{COLOR_RESET}  {"Yes (" + swallow_detail + ")" if diff_swallowing else "None"}
🩸 {COLOR_BOLD}Pain/Bleeding/Lump:{COLOR_RESET}  {"Yes (" + bleeding_detail + ")" if has_bleeding else "None"}
--------------------------------------------------
⚖️  {COLOR_BOLD}Assessed Risk Level:{COLOR_RESET} {risk_display}
🔎 {COLOR_BOLD}Key Risk Factors:{COLOR_RESET}    {reasons_desc}
--------------------------------------------------
{advice}
==================================================
"""
    return report

# Load API key from environment variable
GOOGLE_API_KEY = os.environ.get("GEMINI_API_KEY")

# Initialize the Gemini client if available
client = None
if GOOGLE_API_KEY:
    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)
    except Exception:
        pass

# Define the system prompt for Oral Cancer Screening
system_prompt = """You are OralGuard, an expert AI assistant specialized in oral cancer screening, working under the guidance of Dr. Urja Sunil Ahuja. Your goal is to guide the user/patient through a friendly, compassionate, and structured oral health screening.

Follow these instructions strictly:

STEP 1: INFORMATION GATHERING
Collect the following information, asking only ONE question at a time. Never ask multiple questions in a single prompt.
1. Greet the patient warmly, and ask for their name and age.
2. Ask: "Have you noticed any mouth sores, ulcers, or any unusual white or red patches in your mouth recently?"
3. If they have sores/ulcers/patches, ask: "Which one do you have (sores, ulcers, or patches)?"
4. If they have sores/ulcers/patches, ask: "Could you tell me how long they have been present (in weeks)?"
5. Ask: "Do you use tobacco in any form (like cigarettes, bidis, chewing tobacco), pan masala, betel nut (supari), or gutka?"
6. If they use tobacco, ask: "Which form of tobacco or substance do you use?"
7. If they use tobacco, ask: "For how many years have you been using them?"
8. Ask: "Are you experiencing any difficulty swallowing food or liquids (dysphagia), or any difficulty opening your mouth wide (trismus)?"
9. If they have difficulty swallowing/opening mouth, ask: "Could you tell me more — is it difficulty swallowing, difficulty opening your mouth, or both? And how long have you been experiencing this?"
10. Ask: "Are you experiencing any pain, a burning sensation, or any unexplained bleeding in your mouth?"
11. If they have pain/burning/bleeding, ask: "Could you tell me specifically — is it pain, burning sensation, bleeding, or a combination? Where exactly in your mouth? And since when?"

DIALOGUE AND PROBING RULES:
- Ask only ONE question at a time.
- Do not jump to the next step or next question until you have collected both the specific symptom details and the duration/history for the current question. If the user answers just "yes" to any question that requires details (like sores/ulcers/patches, tobacco form/duration, swallowing/opening difficulty, or pain/burning/bleeding), you MUST probe immediately for the specific details before moving on. A simple "yes" without details should never trigger HIGH RISK classification; you must get specific details first.

STEP 2: RISK ASSESSMENT
Once you have gathered all the necessary information, evaluate the risk level based on the following criteria:

INSUFFICIENT INFORMATION RULE:
- If the patient refuses to answer, skips, or fails to provide essential details for any of the questions from Step 1 (such as whether they have mouth sores/ulcers/patches and their duration, or whether they use tobacco, what form, and since when, or difficulty swallowing, or unexplained bleeding/lumps), you MUST output exactly:
  "INSUFFICIENT INFORMATION: I apologize, but I do not have enough complete details to perform a safe risk assessment. Specifically, I am missing: [insert list of specific missing details here, e.g. duration of mouth sores, tobacco use duration]. Let us restart the questionnaire so I can guide you properly."
  Do not provide any risk category (High/Medium/Low) or care recommendations in this case.

Risk level evaluation criteria:
- HIGH RISK:
  - Any mouth sore, ulcer, or lesion lasting more than 4 weeks.
  - Presence of red (erythroplakia) or white (leukoplakia) patches in the mouth.
  - History of tobacco, gutka, or betel nut use for more than 5 years.
  - Difficulty swallowing (dysphagia) or difficulty opening the mouth (trismus).
  - Unexplained bleeding or a growing lump in the mouth.
- MEDIUM RISK:
  - Classify as MEDIUM RISK if tobacco use is present (but less than 5 years) OR if a mouth sore has lasted 2 to 4 weeks (without meeting high risk criteria) OR if pain or burning sensation is present (without meeting high risk criteria).
- LOW RISK:
  - Classify as LOW RISK if there is NO tobacco use, NO white/red patches, NO difficulty swallowing or opening the mouth, NO unexplained bleeding, AND any mouth sore or ulcer present has lasted LESS than 2 weeks (or no sore is present).

STEP 3: CARE ADVICE
Based on the risk level, provide the corresponding recommendation:
- HIGH RISK: Suggest an urgent referral to an oral surgeon or specialist within 1 week for a clinical evaluation/biopsy. Emphasize the importance without causing undue panic.
- MEDIUM RISK: Recommend visiting a dentist within 2 to 4 weeks for a detailed checkup and monitoring.
- LOW RISK: Recommend standard oral hygiene practices and regular dental checkups every 6 months.

Tone: Warm, empathetic, professional, and reassuring. Speak in simple, non-medical terms where possible."""

# Offline Demo Mode logic (in case API is unavailable)
def run_offline_demo():
    print("\n" + "=" * 50)
    print("🦷  ORALGUARD - Offline Demo Mode (Compassionate Simulation)")
    print("=" * 50)
    
    def get_input(prompt_text):
        typewriter_print(prompt_text, delay=0.008)
        val = input(f"{COLOR_BOLD}{COLOR_WHITE}Patient: {COLOR_RESET}").strip()
        if val.lower() == 'quit':
            typewriter_print(f"\n{COLOR_BOLD}{COLOR_CYAN}OralGuard: Thank you for using OralGuard! Stay healthy! 🦷{COLOR_RESET}")
            sys.exit(0)
        return val

    # 1. Name and age
    intro = ("OralGuard: Hello! I am OralGuard, Dr. Urja's AI oral cancer screening assistant. \n"
             "I will ask you a few questions to understand your oral health. Don't worry, this is a friendly checkup.\n"
             "May I know your name and age? (e.g., Jane, 45 or type 'quit' to exit): ")
    
    name = ""
    age = 0
    while not name or age <= 0:
        name_age_input = get_input(intro)
        if name_age_input:
            parts = [p.strip() for p in name_age_input.split(',')]
            if len(parts) >= 2:
                name = parts[0]
                nums = [int(s) for s in parts[1].split() if s.isdigit()]
                if nums:
                    age = nums[0]
            else:
                nums = [int(s) for s in name_age_input.split() if s.isdigit()]
                if nums:
                    age = nums[0]
                    name_words = [w for w in name_age_input.split() if not w.isdigit()]
                    name = " ".join(name_words).replace(',', '').strip()
                else:
                    name = name_age_input.strip()

        if not name or age <= 0:
            print("\n" + "=" * 50)
            print(f"{COLOR_BOLD}{COLOR_RED}⚠️  INSUFFICIENT INFORMATION{COLOR_RESET}")
            print("=" * 50)
            typewriter_print(f"{COLOR_BOLD}{COLOR_CYAN}OralGuard: I apologize, but I did not receive both your name and age correctly.{COLOR_RESET}")
            typewriter_print(f"{COLOR_BOLD}{COLOR_CYAN}Please provide both your name and age (e.g., Jane, 45).{COLOR_RESET}")
            print("=" * 50 + "\n")
        
    # 2. Sore presence
    sore_q = f"\nOralGuard: Have you noticed any mouth sores, ulcers, or any unusual white or red patches in your mouth recently? (yes/no or type 'quit' to exit): "
    
    has_sores = False
    has_patches = False
    sore_weeks = 0
    sore_type = "None"
    
    while True:
        sore_ans = get_input(sore_q).lower()
        
        if "no" in sore_ans or "n" == sore_ans or "none" in sore_ans or "nope" in sore_ans:
            has_sores = False
            break
        elif "yes" in sore_ans or "y" == sore_ans or "yeah" in sore_ans or "yep" in sore_ans:
            has_sores = True
            
            # Loop for specific type
            type_ok = False
            while not type_ok:
                type_ans = get_input("\nOralGuard: Which one do you have (mouth sores, ulcers, or patches)? (or type 'quit' to exit): ").lower()
                if any(word in type_ans for word in ["sore", "ulcer", "patch", "white", "red", "yes", "y"]):
                    has_patches = "patch" in type_ans or "white" in type_ans or "red" in type_ans
                    sore_type = type_ans
                    type_ok = True
                else:
                    print("\n" + "=" * 50)
                    print(f"{COLOR_BOLD}{COLOR_RED}⚠️  INSUFFICIENT INFORMATION{COLOR_RESET}")
                    print("=" * 50)
                    typewriter_print(f"{COLOR_BOLD}{COLOR_CYAN}OralGuard: Please specify whether you have sores, ulcers, or white/red patches.{COLOR_RESET}")
                    print("=" * 50 + "\n")
                    
            # Loop for duration
            dur_ok = False
            while not dur_ok:
                dur_q = "\nOralGuard: If so, could you tell me how long they have been present (in weeks)? (or type 'quit' to exit): "
                dur_ans = get_input(dur_q).lower()
                nums = [int(s) for s in dur_ans.split() if s.isdigit()]
                if nums:
                    sore_weeks = nums[0]
                    dur_ok = True
                else:
                    print("\n" + "=" * 50)
                    print(f"{COLOR_BOLD}{COLOR_RED}⚠️  INSUFFICIENT INFORMATION{COLOR_RESET}")
                    print("=" * 50)
                    typewriter_print(f"{COLOR_BOLD}{COLOR_CYAN}OralGuard: Please specify the duration as a number of weeks.{COLOR_RESET}")
                    print("=" * 50 + "\n")
            break
        else:
            print("\n" + "=" * 50)
            print(f"{COLOR_BOLD}{COLOR_RED}⚠️  INSUFFICIENT INFORMATION{COLOR_RESET}")
            print("=" * 50)
            typewriter_print(f"{COLOR_BOLD}{COLOR_CYAN}OralGuard: I apologize, but I did not receive a clear response. Please answer 'yes' or 'no'.{COLOR_RESET}")
            print("=" * 50 + "\n")

    # 3. Tobacco presence
    tobacco_q = f"\nOralGuard: Do you use tobacco in any form (like cigarettes, bidis, chewing tobacco), pan masala, betel nut (supari), or gutka? (yes/no or type 'quit' to exit): "
    
    has_tobacco = False
    tobacco_years = 0
    tobacco_type = "None"
    
    while True:
        tobacco_ans = get_input(tobacco_q).lower()
        
        if "no" in tobacco_ans or "n" == tobacco_ans or "none" in tobacco_ans or "nope" in tobacco_ans:
            has_tobacco = False
            if name:
                typewriter_print(f"\n{COLOR_BOLD}{COLOR_CYAN}OralGuard: That's good to hear, {name}. Thank you for sharing that information.{COLOR_RESET}")
            break
        elif "yes" in tobacco_ans or "y" == tobacco_ans or "yeah" in tobacco_ans or "yep" in tobacco_ans:
            has_tobacco = True
            
            # Loop for specific form
            form_ok = False
            while not form_ok:
                form_ans = get_input("\nOralGuard: Which form of tobacco or substance do you use? (or type 'quit' to exit): ").lower()
                if any(word in form_ans for word in ["tobacco", "cigarette", "bidi", "chewing", "masala", "nut", "supari", "gutka", "yes", "y"]):
                    tobacco_type = form_ans
                    form_ok = True
                else:
                    print("\n" + "=" * 50)
                    print(f"{COLOR_BOLD}{COLOR_RED}⚠️  INSUFFICIENT INFORMATION{COLOR_RESET}")
                    print("=" * 50)
                    typewriter_print(f"{COLOR_BOLD}{COLOR_CYAN}OralGuard: Please specify which form you use (e.g. cigarettes, chewing tobacco, gutka).{COLOR_RESET}")
                    print("=" * 50 + "\n")
                    
            # Loop for years
            years_ok = False
            while not years_ok:
                years_ans = get_input("\nOralGuard: And for how many years you've been using them? (or type 'quit' to exit): ").lower()
                nums = [int(s) for s in years_ans.split() if s.isdigit()]
                if nums:
                    tobacco_years = nums[0]
                    years_ok = True
                else:
                    print("\n" + "=" * 50)
                    print(f"{COLOR_BOLD}{COLOR_RED}⚠️  INSUFFICIENT INFORMATION{COLOR_RESET}")
                    print("=" * 50)
                    typewriter_print(f"{COLOR_BOLD}{COLOR_CYAN}OralGuard: Please specify the number of years as a number.{COLOR_RESET}")
                    print("=" * 50 + "\n")
            break
        else:
            print("\n" + "=" * 50)
            print(f"{COLOR_BOLD}{COLOR_RED}⚠️  INSUFFICIENT INFORMATION{COLOR_RESET}")
            print("=" * 50)
            typewriter_print(f"{COLOR_BOLD}{COLOR_CYAN}OralGuard: I apologize, but I did not receive a clear response. Please answer 'yes' or 'no'.{COLOR_RESET}")
            print("=" * 50 + "\n")

    # 4. Swallowing / opening mouth
    swallow_q = ("\nOralGuard: Next, I'd like to ask: Are you experiencing any difficulty swallowing food or liquids (dysphagia), "
                 "or any difficulty opening your mouth wide (trismus)? (yes/no or type 'quit' to exit): ")
    
    diff_swallowing = False
    swallow_detail = "None"
    swallow_duration = ""
    
    while True:
        swallow_ans = get_input(swallow_q).lower()
        
        if "yes" in swallow_ans or "y" == swallow_ans or "yeah" in swallow_ans or "yep" in swallow_ans:
            detail_ok = False
            while not detail_ok:
                detail_ans = get_input("\nOralGuard: Could you tell me more — is it difficulty swallowing, difficulty opening your mouth, or both? And how long have you been experiencing this? (or type 'quit' to exit): ").lower()
                
                has_swallow = "swallow" in detail_ans or "dysphagia" in detail_ans
                has_trismus = "open" in detail_ans or "trismus" in detail_ans or "mouth" in detail_ans or "wide" in detail_ans
                has_both = "both" in detail_ans or (has_swallow and has_trismus)
                
                nums = [int(s) for s in detail_ans.split() if s.isdigit()]
                has_duration = len(nums) > 0 or any(word in detail_ans for word in ["week", "month", "year", "day", "since", "long", "ago"])
                
                if (has_swallow or has_trismus or has_both) and has_duration:
                    diff_swallowing = True
                    swallow_detail = "difficulty swallowing" if has_swallow else "difficulty opening mouth wide"
                    if has_both:
                        swallow_detail = "both difficulty swallowing and difficulty opening mouth wide"
                    swallow_duration = detail_ans
                    detail_ok = True
                else:
                    print("\n" + "=" * 50)
                    print(f"{COLOR_BOLD}{COLOR_RED}⚠️  INSUFFICIENT INFORMATION{COLOR_RESET}")
                    print("=" * 50)
                    typewriter_print(f"{COLOR_BOLD}{COLOR_CYAN}OralGuard: Please specify what difficulty you have (swallowing, opening mouth, or both) and how long you've had it.{COLOR_RESET}")
                    print("=" * 50 + "\n")
            break
        elif "no" in swallow_ans or "n" == swallow_ans or "none" in swallow_ans or "nope" in swallow_ans:
            diff_swallowing = False
            if name:
                typewriter_print(f"\n{COLOR_BOLD}{COLOR_CYAN}OralGuard: Thank you, {name}. That's helpful to know.{COLOR_RESET}")
            break
        else:
            print("\n" + "=" * 50)
            print(f"{COLOR_BOLD}{COLOR_RED}⚠️  INSUFFICIENT INFORMATION{COLOR_RESET}")
            print("=" * 50)
            typewriter_print(f"{COLOR_BOLD}{COLOR_CYAN}OralGuard: I apologize, but I did not receive a clear response. Please answer 'yes' or 'no'.{COLOR_RESET}")
            print("=" * 50 + "\n")
    
    # 5. Pain / bleeding
    bleeding_q = ("\nOralGuard: Finally, could you tell me if you are experiencing any pain, a burning sensation, "
                  "or any unexplained bleeding in your mouth? (yes/no or type 'quit' to exit): ")
    
    has_pain = False
    has_burning = False
    has_bleeding = False
    bleeding_detail = "None"
    bleeding_location = ""
    bleeding_duration = ""
    
    while True:
        bleeding_ans = get_input(bleeding_q).lower()
        
        if "yes" in bleeding_ans or "y" == bleeding_ans or "yeah" in bleeding_ans or "yep" in bleeding_ans:
            detail_ok = False
            while not detail_ok:
                detail_ans = get_input("\nOralGuard: Could you tell me specifically — is it pain, burning sensation, bleeding, or a combination? Where exactly in your mouth? And since when? (or type 'quit' to exit): ").lower()
                
                h_pain = "pain" in detail_ans
                h_burning = "burning" in detail_ans or "sensation" in detail_ans or "burn" in detail_ans
                h_bleed = "bleed" in detail_ans or "blood" in detail_ans
                
                has_location = any(word in detail_ans for word in ["tongue", "cheek", "lip", "gum", "throat", "roof", "floor", "palate", "mouth", "inside", "side", "left", "right", "back", "front"])
                
                nums = [int(s) for s in detail_ans.split() if s.isdigit()]
                has_dur = len(nums) > 0 or any(word in detail_ans for word in ["week", "month", "year", "day", "since", "long", "ago"])
                
                if (h_pain or h_burning or h_bleed) and has_location and has_dur:
                    has_pain = h_pain
                    has_burning = h_burning
                    has_bleeding = h_bleed
                    bleeding_detail = detail_ans
                    detail_ok = True
                else:
                    print("\n" + "=" * 50)
                    print(f"{COLOR_BOLD}{COLOR_RED}⚠️  INSUFFICIENT INFORMATION{COLOR_RESET}")
                    print("=" * 50)
                    typewriter_print(f"{COLOR_BOLD}{COLOR_CYAN}OralGuard: Please specify the symptom (pain, burning, bleeding, or combination), the location, and since when it started.{COLOR_RESET}")
                    print("=" * 50 + "\n")
            
            if name:
                typewriter_print(f"\n{COLOR_BOLD}{COLOR_CYAN}OralGuard: Thank you, {name}, for answering all my questions thoroughly and honestly. I have all the information I need now.{COLOR_RESET}")
            break
        elif "no" in bleeding_ans or "n" == bleeding_ans or "none" in bleeding_ans or "nope" in bleeding_ans:
            has_bleeding = False
            has_pain = False
            has_burning = False
            if name:
                typewriter_print(f"\n{COLOR_BOLD}{COLOR_CYAN}OralGuard: Thank you, {name}, for answering all my questions thoroughly and honestly. I have all the information I need now.{COLOR_RESET}")
            break
        else:
            print("\n" + "=" * 50)
            print(f"{COLOR_BOLD}{COLOR_RED}⚠️  INSUFFICIENT INFORMATION{COLOR_RESET}")
            print("=" * 50)
            typewriter_print(f"{COLOR_BOLD}{COLOR_CYAN}OralGuard: I apologize, but I did not receive a clear response. Please answer 'yes' or 'no'.{COLOR_RESET}")
            print("=" * 50 + "\n")

    # Calculate Risk
    risk = "LOW RISK"
    reasons = []
    
    if sore_weeks > 4:
        risk = "HIGH RISK"
        reasons.append("a mouth sore/ulcer present for more than 4 weeks")
    if has_patches:
        risk = "HIGH RISK"
        reasons.append("white or red patches in the mouth")
    if tobacco_years > 5:
        risk = "HIGH RISK"
        reasons.append("history of tobacco/gutka use for more than 5 years")
    if diff_swallowing:
        risk = "HIGH RISK"
        reasons.append(f"difficulty swallowing or opening your mouth ({swallow_detail})")
    if has_bleeding:
        risk = "HIGH RISK"
        reasons.append(f"unexplained bleeding or a lump in your mouth ({bleeding_detail})")
        
    if risk != "HIGH RISK":
        if has_tobacco and tobacco_years <= 5:
            risk = "MEDIUM RISK"
            reasons.append("tobacco/gutka use under 5 years")
        if 2 <= sore_weeks <= 4:
            risk = "MEDIUM RISK"
            reasons.append("a mouth sore/ulcer present for 2 to 4 weeks")
        if has_pain or has_burning:
            risk = "MEDIUM RISK"
            reasons.append("unexplained pain or burning sensation in the mouth")
            
    if risk == "LOW RISK":
        if sore_weeks < 2 and sore_weeks > 0:
            reasons.append("a mouth sore present for less than 2 weeks with no other risk factors")
        else:
            reasons.append("no history of tobacco use, white/red patches, bleeding, or long-standing sores")

    # Build report text
    report_text = build_report_summary(
        name=name, age=age, 
        has_sores=has_sores, sore_type=sore_type, sore_weeks=sore_weeks,
        has_tobacco=has_tobacco, tobacco_type=tobacco_type, tobacco_years=tobacco_years,
        diff_swallowing=diff_swallowing, swallow_detail=swallow_detail, swallow_duration=swallow_duration,
        has_bleeding=has_bleeding, bleeding_detail=bleeding_detail,
        risk=risk, reasons=reasons
    )
    
    # Print the report card
    print(report_text)
    
    # Save Report option
    export_ans = get_input("\nOralGuard: Would you like to save this screening report as a text file? (yes/no): ").lower()
    if "yes" in export_ans or "y" == export_ans or "yeah" in export_ans:
        # Strip ANSI codes for text file saving
        clean_report = report_text
        for code in [COLOR_RESET, COLOR_BOLD, COLOR_CYAN, COLOR_GREEN, COLOR_YELLOW, COLOR_RED, COLOR_MAGENTA, COLOR_WHITE]:
            clean_report = clean_report.replace(code, "")
        
        filename = f"oralguard_report_{name.replace(' ', '_')}.txt"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(clean_report)
            typewriter_print(f"\n{COLOR_BOLD}{COLOR_GREEN}💾 [System: Report successfully saved to local file: {filename}]{COLOR_RESET}")
        except Exception as e:
            typewriter_print(f"\n{COLOR_BOLD}{COLOR_RED}❌ Error saving file: {e}{COLOR_RESET}")

# Helper function to call the API with retry logic and fallback mechanisms
def generate_with_retry(client_obj, model, contents, config, max_retries=3):
    global GOOGLE_API_KEY, client
    attempt = 0
    while True:
        if not client_obj:
            print(f"\n{COLOR_BOLD}{COLOR_RED}❌ Error: No active Gemini API Client (missing API key).{COLOR_RESET}")
            print("\nPlease choose how you'd like to proceed:")
            print("1. Enter a Gemini API Key to run online.")
            print("2. Run the Offline Demo Mode (local rules simulation).")
            choice = input(f"{COLOR_BOLD}{COLOR_WHITE}Select option (1 or 2): {COLOR_RESET}").strip()
            
            if choice == "1":
                new_key = input(f"{COLOR_BOLD}{COLOR_WHITE}Paste your Gemini API Key: {COLOR_RESET}").strip()
                if new_key:
                    GOOGLE_API_KEY = new_key
                    try:
                        client = genai.Client(api_key=GOOGLE_API_KEY)
                        client_obj = client
                        attempt = 0
                        continue
                    except Exception as ex:
                        print(f"❌ Failed to initialize client: {ex}")
                        client = None
                        client_obj = None
            
            # Default fallback to offline demo mode
            print(f"\n{COLOR_BOLD}{COLOR_CYAN}Switching to Offline Demo Mode...{COLOR_RESET}")
            run_offline_demo()
            sys.exit(0)
            
        try:
            return client_obj.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
        except errors.APIError as e:
            # 429 is Resource Exhausted / Rate Limit
            if e.code == 429 or "RESOURCE_EXHAUSTED" in str(e):
                attempt += 1
                if attempt <= max_retries:
                    # Attempt to extract exact wait time suggested by Gemini API
                    match = re.search(r"Please retry in ([\d\.]+)s", e.message)
                    wait_time = float(match.group(1)) + 1.0 if match else 5.0 * (2 ** (attempt - 1))
                    
                    print(f"\n{COLOR_BOLD}{COLOR_MAGENTA}⚠️  [System: API Rate Limit hit. Needs to wait {wait_time:.1f} seconds before retrying.]{COLOR_RESET}")
                    print("Please choose how you'd like to proceed:")
                    print("  [Press Enter]  - Wait and retry automatically.")
                    print("  [Type 2]       - Skip wait and switch to Offline Demo Mode immediately.")
                    choice = input(f"{COLOR_BOLD}{COLOR_WHITE}Selection: {COLOR_RESET}").strip()
                    
                    if choice == "2":
                        print(f"\n{COLOR_BOLD}{COLOR_CYAN}Switching to Offline Demo Mode...{COLOR_RESET}")
                        run_offline_demo()
                        sys.exit(0)
                        
                    print(f"Waiting {wait_time:.1f} seconds...")
                    time.sleep(wait_time)
                    continue
                
                # Quota completely exhausted
                print(f"\n{COLOR_BOLD}{COLOR_RED}⚠️  [System: API Quota exhausted for the current key.]{COLOR_RESET}")
            else:
                # Other API errors (e.g. Invalid API Key)
                print(f"\n{COLOR_BOLD}{COLOR_RED}❌ API Error ({e.code}): {e.message}{COLOR_RESET}")
            
            # Prompt user for fallback key or offline mode
            print("\nPlease choose how you'd like to proceed:")
            print("1. Enter a different Gemini API Key to retry.")
            print("2. Run the Offline Demo Mode (local rules simulation).")
            choice = input(f"{COLOR_BOLD}{COLOR_WHITE}Select option (1 or 2): {COLOR_RESET}").strip()
            
            if choice == "1":
                new_key = input(f"{COLOR_BOLD}{COLOR_WHITE}Paste your Gemini API Key: {COLOR_RESET}").strip()
                if new_key:
                    GOOGLE_API_KEY = new_key
                    client = genai.Client(api_key=GOOGLE_API_KEY)
                    client_obj = client # update local reference
                    attempt = 0 # reset attempts
                    continue
            
            # Default fallback to offline demo mode
            print(f"\n{COLOR_BOLD}{COLOR_CYAN}Switching to Offline Demo Mode...{COLOR_RESET}")
            run_offline_demo()
            sys.exit(0)

print("=" * 50)
print("🦷  ORALGUARD - Oral Cancer Screening Assistant")
print("    Under the guidance of Dr. Urja Sunil Ahuja")
print("=" * 50)
print("Type 'quit' to exit the screening.\n")

# Use types.Content and types.Part to construct the conversation history
history = []

# Initial instruction to get the assistant to start the screening
initial_prompt = "Please greet the patient warmly, introduce yourself as OralGuard, and ask for their name and age to begin the screening."

# Add user's prompt as the first message in the history using types.Content
history.append(
    types.Content(
        role="user",
        parts=[types.Part.from_text(text=initial_prompt)]
    )
)

# Get the initial greeting from Gemini using the retry wrapper
response = generate_with_retry(
    client_obj=client,
    model="gemini-2.0-flash",
    contents=history,
    config=types.GenerateContentConfig(
        system_instruction=system_prompt
    )
)

greeting = response.text
sys.stdout.write(f"{COLOR_BOLD}{COLOR_CYAN}OralGuard: {COLOR_RESET}")
typewriter_print(greeting)
print()

# Add the model's greeting to the history
history.append(
    types.Content(
        role="model",
        parts=[types.Part.from_text(text=greeting)]
    )
)

# Main conversation loop
while True:
    try:
        # Style Patient prompt
        user_input = input(f"{COLOR_BOLD}{COLOR_WHITE}Patient: {COLOR_RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        typewriter_print(f"\n\n{COLOR_BOLD}{COLOR_CYAN}OralGuard: Thank you for using OralGuard! Stay healthy! 🦷{COLOR_RESET}")
        break

    if not user_input:
        continue

    if user_input.lower() == "quit":
        typewriter_print(f"\n{COLOR_BOLD}{COLOR_CYAN}OralGuard: Thank you for using OralGuard! Stay healthy! 🦷{COLOR_RESET}")
        
        save_transcript = input(f"\n{COLOR_BOLD}{COLOR_WHITE}Would you like to save the conversation transcript to a text file? (yes/no): {COLOR_RESET}").strip().lower()
        if "yes" in save_transcript or "y" == save_transcript or "yeah" in save_transcript:
            filename = "oralguard_chat_transcript.txt"
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write("="*50 + "\n")
                    f.write("🦷 ORALGUARD CONVERSATION TRANSCRIPT\n")
                    f.write("="*50 + "\n\n")
                    for message in history:
                        role = "Patient" if message.role == "user" else "OralGuard"
                        content = message.parts[0].text
                        if "Please greet the patient warmly" in content:
                            continue
                        f.write(f"{role}: {content}\n\n")
                typewriter_print(f"\n{COLOR_BOLD}{COLOR_GREEN}💾 Transcript successfully saved to: {filename}{COLOR_RESET}")
            except Exception as ex:
                typewriter_print(f"\n{COLOR_BOLD}{COLOR_RED}Error saving transcript: {ex}{COLOR_RESET}")
        break

    # Append patient response to history
    history.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_input)]
        )
    )

    # Call Gemini using the retry wrapper
    response = generate_with_retry(
        client_obj=client,
        model="gemini-2.0-flash",
        contents=history,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt
        )
    )

    reply = response.text
    # Print reply with typewriter effect and cyan style
    sys.stdout.write(f"\n{COLOR_BOLD}{COLOR_CYAN}OralGuard: {COLOR_RESET}")
    typewriter_print(reply)
    print()

    # Append model reply to history
    history.append(
        types.Content(
            role="model",
            parts=[types.Part.from_text(text=reply)]
        )
    )