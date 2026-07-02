import os
import sys
import time
from agent import OralGuardAgent
from triage_engine import validate_inputs, assess_risk, get_recommended_advice, generate_partial_report, explain_recommendation

SESSION_FILE = "oralguard_session.json"

try:
    if os.name == 'nt':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
except Exception:
    pass

COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_CYAN = "\033[1;36m"
COLOR_GREEN = "\033[1;32m"
COLOR_YELLOW = "\033[1;33m"
COLOR_RED = "\033[1;31m"
COLOR_WHITE = "\033[1;37m"

def typewriter_print(text, delay=0.005):
    i = 0
    while i < len(text):
        if text[i] == "\033":
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

def main():
    print(f"{COLOR_BOLD}{COLOR_WHITE}" + "=" * 55)
    print("🦷  ORALGUARD - Oral Cancer Screening Agent (Kaggle Edition)")
    print("    Guidance: Dr. Urja Sunil Ahuja")
    print("=" * 55 + f"{COLOR_RESET}\n")

    agent = None
    resumed = False
    
    if os.path.exists(SESSION_FILE):
        print(f"{COLOR_YELLOW}An incomplete screening session was found.{COLOR_RESET}")
        choice = input(f"Would you like to resume or start a new screening? (resume/new): ").strip().lower()
        if choice in ["resume", "r", "yes", "y"]:
            try:
                agent = OralGuardAgent(use_offline=True)
                agent.load_session(SESSION_FILE)
                resumed = True
                print(f"\n{COLOR_GREEN}Session successfully restored.{COLOR_RESET}\n")
            except Exception as e:
                print(f"❌ Error restoring session: {e}. Starting fresh...")
                agent = None
        if not resumed and os.path.exists(SESSION_FILE):
            try:
                os.remove(SESSION_FILE)
            except Exception:
                pass
                
    if not agent:
        print("Choose Mode:")
        print("  1. Online Mode (Conversational LLM - requires Gemini API key)")
        print("  2. Offline Mode (Deterministic Rule-Based Triage)")
        choice = input(f"{COLOR_BOLD}Selection (1 or 2): {COLOR_RESET}").strip()
        
        use_offline = True
        api_key = None
        
        if choice == "1":
            use_offline = False
            api_key_env = os.environ.get("GEMINI_API_KEY")
            if not api_key_env:
                print(f"\n{COLOR_YELLOW}No GEMINI_API_KEY environment variable detected.{COLOR_RESET}")
                api_key_input = input("Paste your Gemini API key (or press Enter to run offline): ").strip()
                if api_key_input:
                    api_key = api_key_input
                else:
                    use_offline = True
                    print(f"{COLOR_CYAN}Running in Offline Mode...{COLOR_RESET}")
        else:
            print(f"{COLOR_CYAN}Running in Offline Mode...{COLOR_RESET}")

        agent = OralGuardAgent(use_offline=use_offline, api_key=api_key)

    print(f"\n{COLOR_BOLD}{COLOR_WHITE}Type 'quit' to save & exit. Type 'why' for clinical rationale.{COLOR_RESET}\n")
    
    if not resumed:
        greeting = agent.get_greeting()
        sys.stdout.write(f"{COLOR_BOLD}{COLOR_CYAN}OralGuard: {COLOR_RESET}")
        typewriter_print(greeting)
        print()
    else:
        re_ask = agent.history[-1]["content"] if agent.history else "Let's continue."
        sys.stdout.write(f"{COLOR_BOLD}{COLOR_CYAN}OralGuard (Continuing): {COLOR_RESET}")
        typewriter_print(re_ask)
        print()
    
    while True:
        try:
            user_input = input(f"{COLOR_BOLD}{COLOR_WHITE}Patient: {COLOR_RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            user_input = "quit"
            
        if not user_input:
            continue
            
        if user_input.lower() in ["quit", "exit"]:
            typewriter_print(f"\n{COLOR_BOLD}{COLOR_CYAN}OralGuard: Saving partial progress and exiting...{COLOR_RESET}")
            
            try:
                agent.save_session(SESSION_FILE)
            except Exception as e:
                print(f"❌ Error saving session file: {e}")
                
            partial_report = generate_partial_report(agent.state)
            typewriter_print(partial_report)
            
            save_t = input(f"\n{COLOR_WHITE}Would you like to save the incomplete chat transcript? (yes/no): {COLOR_RESET}").strip().lower()
            if save_t in ["yes", "y"]:
                filename = "oralguard_incomplete_transcript.txt"
                try:
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write("="*55 + "\n")
                        f.write("🦷 ORALGUARD INCOMPLETE CONVERSATION TRANSCRIPT\n")
                        f.write("="*55 + "\n\n")
                        for msg in agent.history:
                            role = "Patient" if msg["role"] == "user" else "OralGuard"
                            f.write(f"{role}: {msg['content']}\n\n")
                    print(f"💾 Transcript saved to {filename}")
                except Exception as ex:
                    print(f"❌ Error saving transcript: {ex}")
            break
            
        reply = agent.handle_response(user_input)
        sys.stdout.write(f"\n{COLOR_BOLD}{COLOR_CYAN}OralGuard: {COLOR_RESET}")
        
        if "PATIENT SCREENING REPORT SUMMARY" in reply:
            if os.path.exists(SESSION_FILE):
                try:
                    os.remove(SESSION_FILE)
                except Exception:
                    pass
                    
            reply_colored = reply.replace("HIGH RISK", f"{COLOR_BOLD}{COLOR_RED}HIGH RISK{COLOR_RESET}")
            reply_colored = reply_colored.replace("MEDIUM RISK", f"{COLOR_BOLD}{COLOR_YELLOW}MEDIUM RISK{COLOR_RESET}")
            reply_colored = reply_colored.replace("LOW RISK", f"{COLOR_BOLD}{COLOR_GREEN}LOW RISK{COLOR_RESET}")
            typewriter_print(reply_colored)
            
            print(f"\n{COLOR_BOLD}{COLOR_WHITE}Clinical screening complete.{COLOR_RESET}")
            print(f"Options: Type {COLOR_BOLD}'why'{COLOR_RESET} to show clinical rationales, or press Enter to continue.")
            post_choice = input(f"{COLOR_BOLD}Input: {COLOR_RESET}").strip().lower()
            
            if post_choice in ["why", "why?", "why recommend this?", "why do you recommend this?"]:
                risk_level, reasons = assess_risk(agent.state)
                explanation = explain_recommendation(risk_level, reasons)
                print(f"\n{COLOR_CYAN}OralGuard Clinical Explanation:{COLOR_RESET}")
                typewriter_print(explanation)
                print()
                
            save_report = input(f"\n{COLOR_WHITE}Would you like to save this screening report to a file? (yes/no): {COLOR_RESET}").strip().lower()
            if save_report in ["yes", "y"]:
                name = agent.state.get("name", "patient").replace(" ", "_")
                filename = f"oralguard_report_{name}.txt"
                try:
                    with open(filename, "w", encoding="utf-8") as f:
                        clean_reply = reply.replace(COLOR_RED, "").replace(COLOR_GREEN, "").replace(COLOR_YELLOW, "")
                        f.write(clean_reply)
                    print(f"💾 Report saved successfully to {filename}")
                except Exception as e:
                    print(f"❌ Error saving report: {e}")
            break
        else:
            typewriter_print(reply)
            print()

if __name__ == "__main__":
    main()
