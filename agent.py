import os
import re
import json
from google import genai
from google.genai import types
from google.genai import errors
from triage_engine import validate_inputs, assess_risk, get_recommended_advice, explain_recommendation, QUESTION_RATIONALES

SYSTEM_PROMPT = """You are OralGuard, an expert AI assistant specialized in oral cancer screening, working under the guidance of Dr. Urja Sunil Ahuja. Your goal is to guide the user/patient through a friendly, compassionate, and structured oral health screening.

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


class OralGuardAgent:
    def __init__(self, use_offline=False, api_key=None):
        self.use_offline = use_offline
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        
        self.client = None
        if not self.api_key:
            self.use_offline = True
            
        if not self.use_offline:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception:
                self.use_offline = True
        
        self.history = []
        self.state = {
            "name": "",
            "age": 0,
            "has_sores": None,
            "sore_type": "",
            "sore_weeks": -1,
            "has_tobacco": None,
            "tobacco_type": "",
            "tobacco_years": -1,
            "diff_swallowing": None,
            "swallow_detail": "",
            "swallow_duration": "",
            "has_bleeding_q": None,
            "bleeding_detail": ""
        }
        
        self.offline_step = 0
        self.offline_questions = [
            ("greeting", "Hello! I am OralGuard, Dr. Urja's AI oral cancer screening assistant. I will ask you a few questions to understand your oral health. May I know your name and age? (e.g. Jane, 45)"),
            ("has_sores", "Have you noticed any mouth sores, ulcers, or any unusual white or red patches in your mouth recently? (yes/no)"),
            ("sore_type", "Which one do you have (sores, ulcers, or patches)?"),
            ("sore_weeks", "Could you tell me how long they have been present (in weeks)?"),
            ("has_tobacco", "Do you use tobacco in any form (like cigarettes, bidis, chewing tobacco), pan masala, betel nut (supari), or gutka? (yes/no)"),
            ("tobacco_type", "Which form of tobacco or substance do you use?"),
            ("tobacco_years", "For how many years have you been using them?"),
            ("diff_swallowing", "Are you experiencing any difficulty swallowing food or liquids (dysphagia), or any difficulty opening your mouth wide (trismus)? (yes/no)"),
            ("swallow_detail", "Could you tell me more — is it difficulty swallowing, difficulty opening your mouth, or both? And how long have you been experiencing this?"),
            ("has_bleeding_q", "Are you experiencing any pain, a burning sensation, or any unexplained bleeding in your mouth? (yes/no)"),
            ("bleeding_detail", "Could you tell me specifically — is it pain, burning sensation, bleeding, or a combination? Where exactly in your mouth? And since when?")
        ]

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})

    def save_session(self, filepath: str):
        data = {
            "use_offline": self.use_offline,
            "history": self.history,
            "state": self.state,
            "offline_step": self.offline_step
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_session(self, filepath: str):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.use_offline = data.get("use_offline", self.use_offline)
        self.history = data.get("history", [])
        self.state = data.get("state", self.state)
        self.offline_step = data.get("offline_step", 0)
        
        if not self.use_offline and not self.client:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception:
                self.use_offline = True

    def get_greeting(self) -> str:
        if self.use_offline:
            greeting_msg = self.offline_questions[0][1]
            self.add_message("model", greeting_msg)
            self.offline_step = 1
            return greeting_msg
        
        try:
            initial_prompt = "Please greet the patient warmly, introduce yourself as OralGuard, and ask for their name and age to begin the screening."
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=initial_prompt)]
                )
            ]
            
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT
                )
            )
            
            reply = response.text
            self.add_message("model", reply)
            return reply
            
        except Exception:
            self.use_offline = True
            greeting_msg = "⚠️ [API Connection failed. Running in Offline Triage Mode]\n\n" + self.offline_questions[0][1]
            self.add_message("model", greeting_msg)
            self.offline_step = 1
            return greeting_msg

    def handle_response(self, user_input: str) -> str:
        user_input_clean = user_input.strip().lower()
        
        if user_input_clean in ["why", "why?", "why ask this?", "why do you ask this?", "why do you ask?"]:
            is_valid, _ = validate_inputs(self.state)
            if is_valid:
                risk_level, reasons = assess_risk(self.state)
                explanation = explain_recommendation(risk_level, reasons)
                self.add_message("user", user_input)
                self.add_message("model", explanation)
                return explanation
                
            last_question_key = self._get_last_question_key()
            rationale = QUESTION_RATIONALES.get(last_question_key, "This information is collected to construct a clinical profile.")
            
            re_ask = self._get_last_question_text()
            reply = f"ℹ️ *Clinical Rationale*:\n{rationale}\n\n{re_ask}"
            self.add_message("user", user_input)
            self.add_message("model", reply)
            return reply

        if "why do you recommend" in user_input_clean or "why did you recommend" in user_input_clean:
            is_valid, _ = validate_inputs(self.state)
            if is_valid:
                risk_level, reasons = assess_risk(self.state)
                explanation = explain_recommendation(risk_level, reasons)
                self.add_message("user", user_input)
                self.add_message("model", explanation)
                return explanation

        self.add_message("user", user_input)
        
        if self.use_offline:
            return self._handle_offline_step(user_input)
            
        try:
            history_contents = []
            for msg in self.history:
                history_contents.append(
                    types.Content(
                        role="user" if msg["role"] == "user" else "model",
                        parts=[types.Part.from_text(text=msg["content"])]
                    )
                )
                
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=history_contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT
                )
            )
            
            reply = response.text
            self.add_message("model", reply)
            self._attempt_state_extraction(user_input, reply)
            return reply
            
        except Exception:
            self.use_offline = True
            self._transition_to_offline()
            fallback_msg = f"⚠️ [API Connection interrupted. Switching to Offline Triage Mode]\n\n"
            return fallback_msg + self._handle_offline_step(user_input)

    def _get_last_question_key(self) -> str:
        if self.use_offline:
            idx = max(0, self.offline_step - 1)
            return self.offline_questions[idx][0]
            
        last_model_msg = ""
        for msg in reversed(self.history):
            if msg["role"] == "model" and not msg["content"].startswith("ℹ️") and not msg["content"].startswith("⚠️"):
                last_model_msg = msg["content"].lower()
                break
                
        if not last_model_msg:
            return "greeting"
        if "name" in last_model_msg or "age" in last_model_msg:
            return "greeting"
        if "sores" in last_model_msg or "ulcers" in last_model_msg or "patches" in last_model_msg:
            if "which one" in last_model_msg:
                return "sore_type"
            if "how long" in last_model_msg or "weeks" in last_model_msg:
                return "sore_weeks"
            return "has_sores"
        if "tobacco" in last_model_msg or "cigarettes" in last_model_msg or "gutka" in last_model_msg or "masala" in last_model_msg or "bidi" in last_model_msg or "betel" in last_model_msg:
            if "which form" in last_model_msg:
                return "tobacco_type"
            if "how many years" in last_model_msg or "using them" in last_model_msg:
                return "tobacco_years"
            return "has_tobacco"
        if "swallowing" in last_model_msg or "opening" in last_model_msg or "trismus" in last_model_msg or "dysphagia" in last_model_msg:
            if "tell me more" in last_model_msg or "how long" in last_model_msg:
                return "swallow_detail"
            return "diff_swallowing"
        if "pain" in last_model_msg or "burning" in last_model_msg or "bleeding" in last_model_msg:
            if "specifically" in last_model_msg or "where exactly" in last_model_msg:
                return "bleeding_detail"
            return "has_bleeding_q"
            
        return "greeting"

    def _get_last_question_text(self) -> str:
        if self.use_offline:
            idx = max(0, self.offline_step - 1)
            return self.offline_questions[idx][1]
            
        for msg in reversed(self.history):
            if msg["role"] == "model" and not msg["content"].startswith("ℹ️") and not msg["content"].startswith("⚠️"):
                return msg["content"]
        return "Could you please answer the previous question?"

    def _handle_offline_step(self, user_input: str) -> str:
        user_input_lower = user_input.lower().strip()
        prev_step_name = self.offline_questions[self.offline_step - 1][0]
        
        if prev_step_name == "greeting":
            parts = [p.strip() for p in user_input.split(',')]
            name = ""
            age = 0
            if len(parts) >= 2:
                name = parts[0]
                nums = [int(s) for s in parts[1].split() if s.isdigit()]
                if nums:
                    age = nums[0]
            else:
                nums = [int(s) for s in user_input.split() if s.isdigit()]
                if nums:
                    age = nums[0]
                    name_words = [w for w in user_input.split() if not w.isdigit()]
                    name = " ".join(name_words).replace(',', '').strip()
                else:
                    name = user_input.strip()
                    
            if not name or age <= 0:
                self.history.pop()
                return "⚠️ [INSUFFICIENT INFORMATION]\nI apologize, but I did not receive both your name and age correctly. Please provide both (e.g. Jane, 45):"
                
            self.state["name"] = name
            self.state["age"] = age
            self.offline_step = 1
            
        elif prev_step_name == "has_sores":
            if any(word in user_input_lower for word in ["yes", "y", "yeah", "yep"]):
                self.state["has_sores"] = True
                self.offline_step = 2
            elif any(word in user_input_lower for word in ["no", "n", "none", "nope"]):
                self.state["has_sores"] = False
                self.state["sore_type"] = "None"
                self.state["sore_weeks"] = 0
                self.offline_step = 4
            else:
                self.history.pop()
                return "⚠️ [INSUFFICIENT INFORMATION]\nPlease answer 'yes' or 'no' if you noticed mouth sores/ulcers/patches:"
                
        elif prev_step_name == "sore_type":
            if any(word in user_input_lower for word in ["sore", "ulcer", "patch", "white", "red", "yes", "y"]):
                self.state["sore_type"] = user_input
                self.offline_step = 3
            else:
                self.history.pop()
                return "⚠️ [INSUFFICIENT INFORMATION]\nPlease specify what you have (mouth sores, ulcers, or white/red patches):"
                
        elif prev_step_name == "sore_weeks":
            nums = [int(s) for s in user_input.split() if s.isdigit()]
            if nums:
                self.state["sore_weeks"] = nums[0]
                self.offline_step = 4
            else:
                self.history.pop()
                return "⚠️ [INSUFFICIENT INFORMATION]\nPlease specify the duration of the sore as a number of weeks (e.g. 3):"
                
        elif prev_step_name == "has_tobacco":
            if any(word in user_input_lower for word in ["yes", "y", "yeah", "yep"]):
                self.state["has_tobacco"] = True
                self.offline_step = 5
            elif any(word in user_input_lower for word in ["no", "n", "none", "nope"]):
                self.state["has_tobacco"] = False
                self.state["tobacco_type"] = "None"
                self.state["tobacco_years"] = 0
                self.offline_step = 7
            else:
                self.history.pop()
                return "⚠️ [INSUFFICIENT INFORMATION]\nPlease answer 'yes' or 'no' regarding tobacco, gutka, pan masala, or betel nut use:"
                
        elif prev_step_name == "tobacco_type":
            if any(word in user_input_lower for word in ["tobacco", "cigarette", "bidi", "chewing", "masala", "nut", "supari", "gutka", "yes", "y"]):
                self.state["tobacco_type"] = user_input
                self.offline_step = 6
            else:
                self.history.pop()
                return "⚠️ [INSUFFICIENT INFORMATION]\nPlease specify what form of tobacco/substance you use (e.g. gutka, cigarettes):"
                
        elif prev_step_name == "tobacco_years":
            nums = [int(s) for s in user_input.split() if s.isdigit()]
            if nums:
                self.state["tobacco_years"] = nums[0]
                self.offline_step = 7
            else:
                self.history.pop()
                return "⚠️ [INSUFFICIENT INFORMATION]\nPlease specify the duration of use as a number of years (e.g. 6):"
                
        elif prev_step_name == "diff_swallowing":
            if any(word in user_input_lower for word in ["yes", "y", "yeah", "yep"]):
                self.state["diff_swallowing"] = True
                self.offline_step = 8
            elif any(word in user_input_lower for word in ["no", "n", "none", "nope"]):
                self.state["diff_swallowing"] = False
                self.state["swallow_detail"] = "None"
                self.state["swallow_duration"] = "None"
                self.offline_step = 9
            else:
                self.history.pop()
                return "⚠️ [INSUFFICIENT INFORMATION]\nPlease answer 'yes' or 'no' if you experience difficulty swallowing or opening your mouth:"
                
        elif prev_step_name == "swallow_detail":
            has_swallow = "swallow" in user_input_lower or "dysphagia" in user_input_lower
            has_trismus = "open" in user_input_lower or "trismus" in user_input_lower or "mouth" in user_input_lower or "wide" in user_input_lower
            has_both = "both" in user_input_lower or (has_swallow and has_trismus)
            nums = [int(s) for s in user_input.split() if s.isdigit()]
            has_duration = len(nums) > 0 or any(word in user_input_lower for word in ["week", "month", "year", "day", "since", "long", "ago"])
            
            if (has_swallow or has_trismus or has_both) and has_duration:
                self.state["diff_swallowing"] = True
                self.state["swallow_detail"] = "both difficulty swallowing and difficulty opening mouth wide" if has_both else ("difficulty swallowing" if has_swallow else "difficulty opening mouth wide")
                self.state["swallow_duration"] = user_input
                self.offline_step = 9
            else:
                self.history.pop()
                return "⚠️ [INSUFFICIENT INFORMATION]\nPlease specify which difficulty you have (swallowing, opening mouth, or both) and the duration (e.g. swallowing for 2 weeks):"
                
        elif prev_step_name == "has_bleeding_q":
            if any(word in user_input_lower for word in ["yes", "y", "yeah", "yep"]):
                self.state["has_bleeding_q"] = True
                self.offline_step = 10
            elif any(word in user_input_lower for word in ["no", "n", "none", "nope"]):
                self.state["has_bleeding_q"] = False
                self.state["bleeding_detail"] = "None"
                self.offline_step = 11
            else:
                self.history.pop()
                return "⚠️ [INSUFFICIENT INFORMATION]\nPlease answer 'yes' or 'no' if you experience pain, burning, or bleeding:"
                
        elif prev_step_name == "bleeding_detail":
            h_pain = "pain" in user_input_lower
            h_burning = "burning" in user_input_lower or "sensation" in user_input_lower or "burn" in user_input_lower
            h_bleed = "bleed" in user_input_lower or "blood" in user_input_lower or "lump" in user_input_lower or "grow" in user_input_lower
            has_location = any(word in user_input_lower for word in ["tongue", "cheek", "lip", "gum", "throat", "roof", "floor", "palate", "mouth", "inside", "side", "left", "right", "back", "front"])
            nums = [int(s) for s in user_input.split() if s.isdigit()]
            has_dur = len(nums) > 0 or any(word in user_input_lower for word in ["week", "month", "year", "day", "since", "long", "ago"])
            
            if (h_pain or h_burning or h_bleed) and has_location and has_dur:
                self.state["has_bleeding_q"] = True
                self.state["bleeding_detail"] = user_input
                self.offline_step = 11
            else:
                self.history.pop()
                return "⚠️ [INSUFFICIENT INFORMATION]\nPlease specify the symptoms (pain, burning, bleeding, or combination), location, and duration (e.g. bleeding on tongue for 3 days):"

        if self.offline_step >= len(self.offline_questions):
            is_valid, missing_fields = validate_inputs(self.state)
            if not is_valid:
                missing_str = ", ".join(missing_fields)
                report = f"INSUFFICIENT INFORMATION: I apologize, but I do not have enough complete details to perform a safe risk assessment. Specifically, I am missing: [{missing_str}]. Let us restart the questionnaire so I can guide you properly."
                self.add_message("model", report)
                return report
                
            risk_level, reasons = assess_risk(self.state)
            advice = get_recommended_advice(risk_level)
            
            reasons_desc = ", ".join(reasons) if reasons else "No abnormal factors identified"
            report_text = f"""
==================================================
📋  PATIENT SCREENING REPORT SUMMARY
==================================================
👤 Patient Name & Age:  {self.state['name']}, {self.state['age']} years
🩹 Mouth Sores/Ulcers:  {"Yes - " + self.state['sore_type'] + " (" + str(self.state['sore_weeks']) + " weeks)" if self.state['has_sores'] else "None"}
🚬 Tobacco/Gutka Use:   {"Yes - " + self.state['tobacco_type'] + " (" + str(self.state['tobacco_years']) + " years)" if self.state['has_tobacco'] else "None"}
👅 Difficulty opening:  {"Yes (" + self.state['swallow_detail'] + ")" if self.state['diff_swallowing'] else "None"}
🩸 Pain/Bleeding/Lump:  {"Yes (" + self.state['bleeding_detail'] + ")" if self.state['has_bleeding_q'] else "None"}
--------------------------------------------------
⚖️  Assessed Risk Level: {risk_level}
🔎 Key Risk Factors:    {reasons_desc}
--------------------------------------------------
🏥 Dr. Urja's Recommended Next Steps:
{advice}
==================================================
"""
            self.add_message("model", report_text)
            return report_text
            
        next_q = self.offline_questions[self.offline_step][1]
        self.offline_step += 1
        self.add_message("model", next_q)
        return next_q

    def _transition_to_offline(self):
        for msg in self.history:
            if msg["role"] == "user":
                self._attempt_state_extraction(msg["content"], "")
                
        if not self.state["name"] or self.state["age"] <= 0:
            self.offline_step = 1
        elif self.state["has_sores"] is None:
            self.offline_step = 2
        elif self.state["has_sores"] and not self.state["sore_type"]:
            self.offline_step = 3
        elif self.state["has_sores"] and self.state["sore_weeks"] < 0:
            self.offline_step = 4
        elif self.state["has_tobacco"] is None:
            self.offline_step = 5
        elif self.state["has_tobacco"] and not self.state["tobacco_type"]:
            self.offline_step = 6
        elif self.state["has_tobacco"] and self.state["tobacco_years"] < 0:
            self.offline_step = 7
        elif self.state["diff_swallowing"] is None:
            self.offline_step = 8
        elif self.state["diff_swallowing"] and not self.state["swallow_detail"]:
            self.offline_step = 9
        elif self.state["has_bleeding_q"] is None:
            self.offline_step = 10
        elif self.state["has_bleeding_q"] and not self.state["bleeding_detail"]:
            self.offline_step = 11
        else:
            self.offline_step = len(self.offline_questions)

    def _attempt_state_extraction(self, user_text: str, model_text: str):
        user_lower = user_text.lower().strip()
        
        if not self.state["name"] or self.state["age"] <= 0:
            comma_match = re.search(r"([a-zA-Z\s]+),\s*(\d+)", user_text)
            if comma_match:
                self.state["name"] = comma_match.group(1).strip()
                self.state["age"] = int(comma_match.group(2))
            else:
                age_match = re.search(r"\b(\d{1,2})\b", user_text)
                if age_match:
                    self.state["age"] = int(age_match.group(1))
                    cleaned = re.sub(r"\b\d{1,2}\b", "", user_lower)
                    cleaned = re.sub(r"\b(years|old|my|name|is|i\'m|am|patient)\b", "", cleaned)
                    cleaned = cleaned.replace("hello", "").replace("hi", "").replace(",", "").strip()
                    if cleaned:
                        self.state["name"] = cleaned.title()

        if self.state["has_sores"] is None:
            if any(word in user_lower for word in ["yes", "y", "yeah", "yep"]):
                self.state["has_sores"] = True
            elif any(word in user_lower for word in ["no", "n", "none", "nope"]):
                self.state["has_sores"] = False
                self.state["sore_type"] = "None"
                self.state["sore_weeks"] = 0
                
        if self.state["has_sores"]:
            if not self.state["sore_type"]:
                for t in ["ulcer", "patch", "sore"]:
                    if t in user_lower:
                        self.state["sore_type"] = t
            if self.state["sore_weeks"] < 0:
                weeks_match = re.search(r"(\d+)\s*week", user_lower)
                if weeks_match:
                    self.state["sore_weeks"] = int(weeks_match.group(1))
                else:
                    days_match = re.search(r"(\d+)\s*day", user_lower)
                    if days_match:
                        self.state["sore_weeks"] = max(1, int(days_match.group(1)) // 7)

        if self.state["has_tobacco"] is None:
            if any(word in user_lower for word in ["yes", "y", "yeah", "yep"]):
                self.state["has_tobacco"] = True
            elif any(word in user_lower for word in ["no", "n", "none", "nope"]):
                self.state["has_tobacco"] = False
                self.state["tobacco_type"] = "None"
                self.state["tobacco_years"] = 0
                
        if self.state["has_tobacco"]:
            if not self.state["tobacco_type"]:
                for t in ["cigarette", "smoke", "chew", "gutka", "pan", "masala", "supari", "bidi", "tobacco"]:
                    if t in user_lower:
                        self.state["tobacco_type"] = t
            if self.state["tobacco_years"] < 0:
                years_match = re.search(r"(\d+)\s*year", user_lower)
                if years_match:
                    self.state["tobacco_years"] = int(years_match.group(1))

        if self.state["diff_swallowing"] is None:
            if any(word in user_lower for word in ["yes", "y", "yeah", "yep"]):
                self.state["diff_swallowing"] = True
            elif any(word in user_lower for word in ["no", "n", "none", "nope"]):
                self.state["diff_swallowing"] = False
                self.state["swallow_detail"] = "None"
                self.state["swallow_duration"] = "None"
                
        if self.state["diff_swallowing"]:
            if not self.state["swallow_detail"]:
                if "both" in user_lower or ("swallow" in user_lower and "open" in user_lower):
                    self.state["swallow_detail"] = "both difficulty swallowing and difficulty opening mouth wide"
                elif "swallow" in user_lower:
                    self.state["swallow_detail"] = "difficulty swallowing"
                elif "open" in user_lower or "wide" in user_lower or "mouth" in user_lower:
                    self.state["swallow_detail"] = "difficulty opening mouth wide"
            if not self.state["swallow_duration"]:
                dur_match = re.search(r"(\d+)\s*(week|month|year|day)", user_lower)
                if dur_match:
                    self.state["swallow_duration"] = dur_match.group(0)

        if self.state["has_bleeding_q"] is None:
            if any(word in user_lower for word in ["yes", "y", "yeah", "yep"]):
                self.state["has_bleeding_q"] = True
            elif any(word in user_lower for word in ["no", "n", "none", "nope"]):
                self.state["has_bleeding_q"] = False
                self.state["bleeding_detail"] = "None"
                
        if self.state["has_bleeding_q"]:
            if not self.state["bleeding_detail"]:
                self.state["bleeding_detail"] = user_text
