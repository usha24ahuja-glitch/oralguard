import re

QUESTION_RATIONALES = {
    "greeting": "Collecting the patient's name and age helps establish a baseline demographic file. Oral cancer risk increases significantly with age (typically 50+), though younger demographics are increasingly monitored due to shifting habits.",
    "has_sores": "Mouth sores, ulcers, or patches are primary physical indicators. Slipped, thick, or color-altered oral tissues can be early signs of dysplasia or carcinoma.",
    "sore_type": "Differentiating between sores, ulcers, and white/red patches (leukoplakia/erythroplakia) is critical. White or red patches have a higher probability of pre-malignant changes.",
    "sore_weeks": "Duration is a vital clinical metric. Benign traumatic ulcers typically heal within 10-14 days. Any lesion persisting for more than 4 weeks is a significant warning sign requiring biopsy.",
    "has_tobacco": "Tobacco, supari (betel nut), and gutka contain potent carcinogens (like nitrosamines) that chemically alter cells in the oral cavity, representing the leading cause of oral cancer.",
    "tobacco_type": "Different forms of tobacco have distinct risk profiles. Smokeless tobacco, gutka, and pan masala place carcinogens in direct, prolonged contact with the oral mucosa.",
    "tobacco_years": "Carcinogenic exposure is dose-dependent. Using these substances for more than 5 years significantly elevates the risk of cellular mutations.",
    "diff_swallowing": "Difficulty swallowing (dysphagia) or opening the mouth (trismus) suggests structural changes. Tumor invasion into the deep muscles of the jaw or throat restricts mobility.",
    "swallow_detail": "Isolating whether it is trismus, dysphagia, or both helps locate potential tissue involvement, while duration indicates if the restriction is acute or chronic.",
    "has_bleeding_q": "Pain, burning, or unexplained bleeding are clinical warning signs. Malignant lesions often outgrow their blood supply, causing ulceration, tissue breakdown, and bleeding.",
    "bleeding_detail": "Tracking specific symptoms (like bleeding vs. pain), exact location, and onset helps map lesion severity and rules out minor localized dental issues."
}

def validate_inputs(data: dict) -> tuple[bool, list[str]]:
    """
    Validates that all necessary information has been collected.
    Returns (is_valid, list_of_missing_fields_descriptions).
    """
    missing = []
    
    # 1. Name & Age
    if not data.get("name") or not data.get("name").strip():
        missing.append("patient name")
    try:
        age = int(data.get("age", 0))
        if age <= 0:
            missing.append("valid patient age")
    except (ValueError, TypeError):
        missing.append("valid patient age")
        
    # 2. Mouth Sores/Ulcers/Patches
    has_sores = data.get("has_sores")
    if has_sores is None:
        missing.append("whether you have mouth sores, ulcers, or patches recently")
    elif has_sores:
        sore_type = data.get("sore_type")
        if not sore_type or not sore_type.strip() or sore_type.lower() == "none":
            missing.append("specific type of sore (sores, ulcers, or patches)")
            
        try:
            sore_weeks = int(data.get("sore_weeks", -1))
            if sore_weeks < 0:
                missing.append("duration of mouth sores/ulcers (in weeks)")
        except (ValueError, TypeError):
            missing.append("duration of mouth sores/ulcers (in weeks)")
            
    # 3. Tobacco / Gutka / Supari
    has_tobacco = data.get("has_tobacco")
    if has_tobacco is None:
        missing.append("tobacco, pan masala, betel nut, or gutka usage status")
    elif has_tobacco:
        tobacco_type = data.get("tobacco_type")
        if not tobacco_type or not tobacco_type.strip() or tobacco_type.lower() == "none":
            missing.append("specific form of tobacco or substance you use")
            
        try:
            tobacco_years = int(data.get("tobacco_years", -1))
            if tobacco_years < 0:
                missing.append("number of years using tobacco/substances")
        except (ValueError, TypeError):
            missing.append("number of years using tobacco/substances")
            
    # 4. Swallowing (Dysphagia) / Mouth Opening (Trismus)
    diff_swallowing = data.get("diff_swallowing")
    if diff_swallowing is None:
        missing.append("difficulty swallowing or opening mouth status")
    elif diff_swallowing:
        swallow_detail = data.get("swallow_detail")
        swallow_duration = data.get("swallow_duration")
        if not swallow_detail or not swallow_detail.strip() or swallow_detail.lower() == "none":
            missing.append("details of difficulty (swallowing, opening mouth, or both)")
        if not swallow_duration or not swallow_duration.strip():
            missing.append("duration of swallowing or mouth-opening difficulty")
            
    # 5. Pain / Burning / Unexplained Bleeding
    has_bleeding_q = data.get("has_bleeding_q")  # Represents yes/no to the question
    if has_bleeding_q is None:
        missing.append("pain, burning sensation, or unexplained bleeding status")
    elif has_bleeding_q:
        bleeding_detail = data.get("bleeding_detail")
        if not bleeding_detail or not bleeding_detail.strip() or bleeding_detail.lower() == "none":
            missing.append("specific symptom details (pain, burning, bleeding, or combination) and duration")
            
    return len(missing) == 0, missing


def assess_risk(data: dict) -> tuple[str, list[str]]:
    """
    Evaluates the risk level based on clinical screening rules.
    Returns (risk_level, list_of_reasons).
    """
    risk = "LOW RISK"
    reasons = []
    
    # Extract details
    has_sores = data.get("has_sores", False)
    sore_type = str(data.get("sore_type", "")).lower()
    sore_weeks = int(data.get("sore_weeks", 0))
    
    has_tobacco = data.get("has_tobacco", False)
    tobacco_type = str(data.get("tobacco_type", "")).lower()
    tobacco_years = int(data.get("tobacco_years", 0))
    
    diff_swallowing = data.get("diff_swallowing", False)
    swallow_detail = str(data.get("swallow_detail", ""))
    
    has_bleeding_q = data.get("has_bleeding_q", False)
    bleeding_detail = str(data.get("bleeding_detail", "")).lower()
    
    # Analyze patches
    has_patches = "patch" in sore_type or "white" in sore_type or "red" in sore_type
    
    # Parse pain, burning, bleeding, lump from the bleeding_detail
    is_bleeding_or_lump = "bleed" in bleeding_detail or "blood" in bleeding_detail or "lump" in bleeding_detail or "grow" in bleeding_detail
    is_pain_or_burning = "pain" in bleeding_detail or "burn" in bleeding_detail or "sensation" in bleeding_detail
    
    # --- HIGH RISK CRITERIA ---
    if sore_weeks > 4:
        risk = "HIGH RISK"
        reasons.append("a mouth sore/ulcer present for more than 4 weeks")
    if has_patches:
        risk = "HIGH RISK"
        reasons.append("white or red patches in the mouth")
    if tobacco_years > 5:
        risk = "HIGH RISK"
        reasons.append("history of tobacco/gutka/betel nut use for more than 5 years")
    if diff_swallowing:
        risk = "HIGH RISK"
        reasons.append(f"difficulty swallowing or opening your mouth ({swallow_detail})")
    if has_bleeding_q and is_bleeding_or_lump:
        risk = "HIGH RISK"
        reasons.append(f"unexplained bleeding or a lump in your mouth ({bleeding_detail})")
        
    # --- MEDIUM RISK CRITERIA (if not already HIGH RISK) ---
    if risk != "HIGH RISK":
        if has_tobacco and tobacco_years <= 5:
            risk = "MEDIUM RISK"
            reasons.append("tobacco/gutka/betel nut use under 5 years")
        if 2 <= sore_weeks <= 4:
            risk = "MEDIUM RISK"
            reasons.append("a mouth sore/ulcer present for 2 to 4 weeks")
        if has_bleeding_q and is_pain_or_burning:
            risk = "MEDIUM RISK"
            reasons.append("unexplained pain or burning sensation in the mouth")
            
    # --- LOW RISK CRITERIA ---
    if risk == "LOW RISK":
        if 0 < sore_weeks < 2:
            reasons.append("a mouth sore present for less than 2 weeks with no other risk factors")
        else:
            reasons.append("no history of tobacco use, white/red patches, bleeding, or long-standing sores")
            
    return risk, reasons


def get_recommended_advice(risk: str) -> str:
    """
    Returns Dr. Urja's clinical recommendation based on risk.
    """
    if risk == "HIGH RISK":
        return ("I strongly advise you to schedule a visit to an oral surgeon or specialist "
                "within the next week for a professional checkup and clinical evaluation. Please don't worry, but taking "
                "early action is the best path to stay safe.")
    elif risk == "MEDIUM RISK":
        return ("I suggest visiting your dentist within the next 2 to 4 weeks for a detailed checkup and evaluation "
                "to monitor these symptoms and ensure everything heals correctly.")
    else:
        return ("I suggest maintaining standard, healthy oral hygiene habits and scheduling regular dental checkups "
                "every 6 months. This helps keep your mouth healthy and prevents future issues!")


def generate_partial_report(data: dict) -> str:
    """
    Generates a structured clinical report for an incomplete screening session.
    No definitive risk level is assigned.
    """
    completed = []
    missing = []
    
    # Check name & age
    if data.get("name") and int(data.get("age", 0)) > 0:
        completed.append(f"Patient: {data.get('name')}, {data.get('age')} years")
    else:
        missing.append("Patient name and age")
        
    # Check sores
    if data.get("has_sores") is False:
        completed.append("Mouth sores/ulcers/patches: None reported")
    elif data.get("has_sores") is True:
        sore_type = data.get("sore_type")
        sore_weeks = data.get("sore_weeks", -1)
        if sore_type and sore_weeks >= 0:
            completed.append(f"Mouth sores: Yes ({sore_type}, {sore_weeks} weeks)")
        else:
            if not sore_type:
                missing.append("Specific type of mouth sore/patch")
            if sore_weeks < 0:
                missing.append("Duration of mouth sores")
    else:
        missing.append("Presence of mouth sores/ulcers/patches")
        
    # Check tobacco
    if data.get("has_tobacco") is False:
        completed.append("Tobacco/gutka use: None reported")
    elif data.get("has_tobacco") is True:
        t_type = data.get("tobacco_type")
        t_years = data.get("tobacco_years", -1)
        if t_type and t_years >= 0:
            completed.append(f"Tobacco/gutka use: Yes ({t_type}, {t_years} years)")
        else:
            if not t_type:
                missing.append("Specific form of tobacco/substance used")
            if t_years < 0:
                missing.append("Duration of tobacco/substance use")
    else:
        missing.append("Tobacco/gutka/betel nut usage status")
        
    # Check swallowing/mouth opening
    if data.get("diff_swallowing") is False:
        completed.append("Difficulty swallowing/opening mouth: None reported")
    elif data.get("diff_swallowing") is True:
        s_detail = data.get("swallow_detail")
        s_dur = data.get("swallow_duration")
        if s_detail and s_dur:
            completed.append(f"Difficulty swallowing/opening: Yes ({s_detail}, duration: {s_dur})")
        else:
            if not s_detail:
                missing.append("Difficulty details (swallowing/opening/both)")
            if not s_dur:
                missing.append("Duration of swallowing/opening difficulty")
    else:
        missing.append("Difficulty swallowing or opening mouth wide status")
        
    # Check bleeding/pain
    if data.get("has_bleeding_q") is False:
        completed.append("Pain/burning/bleeding symptoms: None reported")
    elif data.get("has_bleeding_q") is True:
        b_detail = data.get("bleeding_detail")
        if b_detail:
            completed.append(f"Pain/burning/bleeding symptoms: Yes ({b_detail})")
        else:
            missing.append("Specific pain/burning/bleeding details and duration")
    else:
        missing.append("Pain, burning, or unexplained bleeding status")

    completed_str = "\n".join([f"  • {c}" for c in completed]) if completed else "  • None"
    missing_str = "\n".join([f"  • {m}" for m in missing]) if missing else "  • None"

    report = f"""
==================================================
⚠️  INCOMPLETE SCREENING DOSSIER
==================================================
This screening session was terminated before completion. 
No definitive clinical risk assessment or final risk score has been generated.

📋 INFORMATION COLLECTED SO FAR:
{completed_str}

🔍 MISSING INFORMATION REQUIRED FOR RISK ASSESSMENT:
{missing_str}

🏥 CLINICAL RECOMMENDATION:
I strongly advise completing the remaining questions of the screening to receive a safe and accurate risk assessment. If you are experiencing concerning symptoms like persistent mouth sores (>4 weeks), difficulty swallowing, or unexplained bleeding, please consult a dentist or oral surgeon directly.
==================================================
"""
    return report


def explain_recommendation(risk_level: str, reasons: list[str]) -> str:
    """
    Returns a clinical, evidence-based explanation detailing why a specific
    recommendation was generated based on the patient's symptoms.
    """
    reasons_str = ", ".join(reasons) if reasons else "no major abnormal indicators"
    explanation = f"Dr. Urja's screening engine has assessed this patient as {risk_level} because of: {reasons_str}.\n\n"
    
    if risk_level == "HIGH RISK":
        explanation += (
            "Clinical Justification:\n"
            "1. Persistent lesions (>4 weeks) or leukoplakia/erythroplakia (white/red patches) are highly correlated with dysplasia and squamous cell carcinoma. They lack normal healing capacity and require immediate biopsy.\n"
            "2. History of tobacco, supari, or gutka use for over 5 years causes sustained chemical trauma to the oral tissue, raising tissue mutation rates.\n"
            "3. Jaw stiffness (trismus) or dysphagia points to deep infiltration of muscle and nerve networks in the jaw or throat, suggesting advanced lesion development.\n"
            "4. Spontaneous or unexplained oral bleeding indicates localized tissue necrosis or vascular erosion.\n\n"
            "Therefore, an immediate referral to an oral surgeon or specialist is strongly recommended to initiate early clinical diagnostic workup."
        )
    elif risk_level == "MEDIUM RISK":
        explanation += (
            "Clinical Justification:\n"
            "1. Short-term tobacco/gutka use (<=5 years) introduces mucosal exposure to chemical carcinogens, raising risks above the baseline population.\n"
            "2. Sores present for 2 to 4 weeks are borderline; while they may be chronic traumatic ulcers, they exceed the normal 10-14 day healing window and must be monitored to ensure complete resolution.\n"
            "3. Pain or burning sensations can be indicators of early-stage inflammatory mucosal conditions, nutritional deficits, or early pre-cancerous lesions.\n\n"
            "Therefore, a dentist checkup within 2-4 weeks is advised to monitor healing progress and decide if further referral is required."
        )
    else:
        explanation += (
            "Clinical Justification:\n"
            "The screening shows no history of tobacco/gutka use, no red/white patches, no jaw movement limitations, no unexplained bleeding, and any reported sores are under 2 weeks old (well within the normal window for minor traumatic ulcers/apthous ulcers).\n\n"
            "Therefore, standard oral hygiene maintenance and routine biannual dental examinations are recommended."
        )
    return explanation
