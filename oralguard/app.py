import streamlit as st
import os
import json
from agent import OralGuardAgent
from triage_engine import assess_risk, validate_inputs, get_recommended_advice, generate_partial_report, explain_recommendation, QUESTION_RATIONALES

SESSION_FILE = "oralguard_session.json"

st.set_page_config(
    page_title="OralGuard | Oral Cancer Risk Screening Assistant",
    page_icon="🦷",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Outfit', sans-serif;
        font-weight: 600;
    }
    
    .clinical-header {
        background: linear-gradient(135deg, #0d3b4c 0%, #005a70 100%);
        padding: 2.5rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px 0 rgba(0, 90, 112, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.1);
        position: relative;
        overflow: hidden;
    }
    .clinical-header::after {
        content: '';
        position: absolute;
        width: 300px;
        height: 300px;
        background: radial-gradient(circle, rgba(0,255,255,0.08) 0%, rgba(0,0,0,0) 70%);
        top: -100px;
        right: -100px;
        pointer-events: none;
    }
    .clinical-title {
        font-size: 2.4rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .clinical-subtitle {
        font-size: 1.05rem;
        color: #9cdbd9;
        margin-top: 0.2rem;
        font-weight: 400;
        letter-spacing: 1px;
    }
    
    .sidebar-card {
        background-color: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        padding: 1.25rem;
        border-radius: 12px;
        margin-bottom: 1rem;
    }
    
    .risk-badge {
        padding: 8px 16px;
        border-radius: 8px;
        font-weight: 700;
        display: inline-block;
        margin-top: 0.5rem;
        font-size: 1.1rem;
        letter-spacing: 0.5px;
    }
    .risk-high {
        background-color: rgba(239, 68, 68, 0.15);
        color: #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .risk-medium {
        background-color: rgba(245, 158, 11, 0.15);
        color: #f59e0b;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }
    .risk-low {
        background-color: rgba(16, 185, 129, 0.15);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    
    .pulse-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 6px;
    }
    .pulse-online {
        background-color: #10b981;
        box-shadow: 0 0 8px #10b981;
        animation: pulse 2s infinite;
    }
    .pulse-offline {
        background-color: #f59e0b;
        box-shadow: 0 0 8px #f59e0b;
        animation: pulse 2.5s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(0.95); opacity: 0.5; }
        50% { transform: scale(1.15); opacity: 1; }
        100% { transform: scale(0.95); opacity: 0.5; }
    }
</style>
""", unsafe_allow_html=True)

if "screening_started" not in st.session_state:
    st.session_state.screening_started = False
if "agent" not in st.session_state:
    st.session_state.agent = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "incomplete_saved" not in st.session_state:
    st.session_state.incomplete_saved = False

st.sidebar.markdown(f"""
<div style="text-align: center; margin-bottom: 1.5rem;">
    <h2 style="margin: 0; font-size: 1.8rem; color: #008080;">🦷 OralGuard</h2>
    <p style="font-size: 0.85rem; color: gray; margin: 0;">CASE ASSESSMENT DASHBOARD</p>
</div>
""", unsafe_allow_html=True)

has_saved_session = os.path.exists(SESSION_FILE)

if not st.session_state.screening_started:
    st.markdown("""
    <div class="clinical-header">
        <h1 class="clinical-title">OralGuard AI Screening Assistant</h1>
        <p class="clinical-subtitle">ORAL CANCER RISK SCREENING ASSISTANT • DR. URJA SUNIL AHUJA</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        ### Oral Cancer Risk Screening Overview
        Welcome to OralGuard. This clinical screening assistant collects details on oral lesions, pain/bleeding, trismus, dysphagia, and tobacco history to calculate patient risk indicators for oral cancer. It runs in two distinct execution environments:
        
        *   🔌 **Online Mode**: Employs conversational reasoning powered by the Gemini 2.0 API under prompt engineering guidelines.
        *   💾 **Offline Mode**: A deterministic, rule-based clinical scoring engine that runs instantly without internet connectivity.
        """)
        
        st.info("💡 **Note**: The offline mode runs entirely on-device and is designed to guarantee safe screening when internet connectivity is restricted or API quota is exhausted.")
        
        if has_saved_session:
            st.markdown("### ⚠️ Saved Session Detected")
            st.warning("OralGuard found an incomplete screening session. You can restore your progress and continue where you left off.")
            
            col_res1, col_res2 = st.columns(2)
            with col_res1:
                if st.button("🔄 Resume Saved Session", use_container_width=True, type="primary"):
                    st.session_state.agent = OralGuardAgent(use_offline=True)
                    st.session_state.agent.load_session(SESSION_FILE)
                    st.session_state.screening_started = True
                    st.session_state.messages = []
                    for m in st.session_state.agent.history:
                        st.session_state.messages.append({"role": m["role"], "content": m["content"]})
                    st.rerun()
            with col_res2:
                if st.button("🗑️ Discard and Start Fresh", use_container_width=True):
                    try:
                        os.remove(SESSION_FILE)
                    except Exception:
                        pass
                    st.rerun()
        
    with col2:
        st.markdown("### Choose Execution Mode")
        mode = st.radio("Screening Mode", ["Online Mode (Gemini API)", "Offline Mode (Rules Engine)"], disabled=has_saved_session)
        
        api_key_input = ""
        if mode == "Online Mode (Gemini API)":
            api_key_input = st.text_input("Gemini API Key (Optional fallback)", type="password", disabled=has_saved_session)
            
        start_btn = st.button("Start fresh Oral Screening", use_container_width=True, type="secondary" if has_saved_session else "primary")
        
        if start_btn:
            use_offline = (mode == "Offline Mode (Rules Engine)")
            st.session_state.agent = OralGuardAgent(
                use_offline=use_offline,
                api_key=api_key_input if api_key_input else None
            )
            st.session_state.screening_started = True
            st.session_state.incomplete_saved = False
            
            greeting = st.session_state.agent.get_greeting()
            st.session_state.messages = [{"role": "model", "content": greeting}]
            st.rerun()

else:
    agent = st.session_state.agent
    status_class = "pulse-offline" if agent.use_offline else "pulse-online"
    status_label = "OFFLINE MODE" if agent.use_offline else "ONLINE MODE"
    
    st.markdown(f"""
    <div class="clinical-header" style="padding: 1.5rem 2rem; margin-bottom: 1.5rem;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 class="clinical-title" style="font-size: 1.8rem;">OralGuard Screening Interface</h1>
                <p class="clinical-subtitle" style="font-size: 0.9rem; margin: 0;">ORAL CANCER RISK SCREENING PROGRAM • DR. URJA SUNIL AHUJA</p>
            </div>
            <div style="background: rgba(255,255,255,0.08); padding: 8px 16px; border-radius: 8px; font-weight: 600; display: flex; align-items: center;">
                <span class="pulse-dot {status_class}"></span>
                <span style="font-size: 0.85rem; letter-spacing: 0.5px; color: white;">{status_label}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown("### 👤 Patient Dossier")
    st.sidebar.markdown(f"**Name**: {agent.state['name'] if agent.state['name'] else 'Pending...'}")
    st.sidebar.markdown(f"**Age**: {str(agent.state['age']) + ' years' if agent.state['age'] > 0 else 'Pending...'}")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔍 Extracted Clinical Data")
    
    sores_desc = "None"
    if agent.state['has_sores'] is True:
        sores_desc = f"⚠️ Yes ({agent.state['sore_type']}, {agent.state['sore_weeks']} weeks)"
    elif agent.state['has_sores'] is False:
        sores_desc = "✅ None"
    st.sidebar.markdown(f"**Mouth Sores/Lesions**: {sores_desc}")
    
    tobacco_desc = "None"
    if agent.state['has_tobacco'] is True:
        tobacco_desc = f"⚠️ Yes ({agent.state['tobacco_type']}, {agent.state['tobacco_years']} years)"
    elif agent.state['has_tobacco'] is False:
        tobacco_desc = "✅ None"
    st.sidebar.markdown(f"**Tobacco/Gutka Use**: {tobacco_desc}")
    
    swallow_desc = "None"
    if agent.state['diff_swallowing'] is True:
        swallow_desc = f"⚠️ Yes ({agent.state['swallow_detail']})"
    elif agent.state['diff_swallowing'] is False:
        swallow_desc = "✅ None"
    st.sidebar.markdown(f"**Dysphagia / Trismus**: {swallow_desc}")
    
    bleeding_desc = "None"
    if agent.state['has_bleeding_q'] is True:
        bleeding_desc = f"⚠️ Yes ({agent.state['bleeding_detail']})"
    elif agent.state['has_bleeding_q'] is False:
        bleeding_desc = "✅ None"
    st.sidebar.markdown(f"**Pain/Bleeding/Lumps**: {bleeding_desc}")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚖️ Real-Time Risk Estimation")
    
    is_valid, _ = validate_inputs(agent.state)
    if is_valid and not st.session_state.incomplete_saved:
        risk_level, reasons = assess_risk(agent.state)
        if risk_level == "HIGH RISK":
            st.sidebar.markdown('<div class="risk-badge risk-high">🔴 HIGH RISK</div>', unsafe_allow_html=True)
        elif risk_level == "MEDIUM RISK":
            st.sidebar.markdown('<div class="risk-badge risk-medium">🟡 MEDIUM RISK</div>', unsafe_allow_html=True)
        else:
            st.sidebar.markdown('<div class="risk-badge risk-low">🟢 LOW RISK</div>', unsafe_allow_html=True)
    elif st.session_state.incomplete_saved:
        st.sidebar.markdown('<div class="risk-badge" style="background-color: rgba(255,255,255,0.08); color: gray; border: 1px dashed gray;">⚠️ INCOMPLETE</div>', unsafe_allow_html=True)
    else:
        st.sidebar.info("Awaiting more clinical data to estimate risk score.")
        
    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)
    restart = st.sidebar.button("Restart Screening", use_container_width=True)
    if restart:
        if os.path.exists(SESSION_FILE):
            try:
                os.remove(SESSION_FILE)
            except Exception:
                pass
        st.session_state.screening_started = False
        st.session_state.agent = None
        st.session_state.messages = []
        st.session_state.incomplete_saved = False
        st.rerun()

    col_chat, col_report = st.columns([3, 2])
    
    with col_chat:
        st.subheader("💬 Interactive Screening Consultation")
        
        for msg in st.session_state.messages:
            avatar = "🏥" if msg["role"] == "model" else "👤"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])
                
        if not is_valid and not st.session_state.incomplete_saved:
            last_key = agent._get_last_question_key()
            if last_key in QUESTION_RATIONALES:
                with st.expander("ℹ️ Clinical Rationale (Why are we asking this?)"):
                    st.info(QUESTION_RATIONALES[last_key])

        if not is_valid and not st.session_state.incomplete_saved:
            chat_col, exit_col = st.columns([4, 1])
            with chat_col:
                user_input = st.chat_input("Enter your response here...")
            with exit_col:
                st.write("")
                if st.button("💾 Save & Exit", use_container_width=True, type="secondary"):
                    agent.save_session(SESSION_FILE)
                    st.session_state.incomplete_saved = True
                    st.rerun()
                    
            if user_input:
                with st.chat_message("user", avatar="👤"):
                    st.markdown(user_input)
                st.session_state.messages.append({"role": "user", "content": user_input})
                
                with st.spinner("OralGuard is processing..."):
                    reply = agent.handle_response(user_input)
                    
                with st.chat_message("model", avatar="🏥"):
                    st.markdown(reply)
                st.session_state.messages.append({"role": "model", "content": reply})
                st.rerun()
        else:
            st.chat_input("Screening complete or saved. Chat input disabled.", disabled=True)

    with col_report:
        st.subheader("📋 Screening Assessment Summary")
        
        if st.session_state.incomplete_saved:
            st.markdown("### ⚠️ SESSION SAVED AS INCOMPLETE")
            st.error("No definitive risk score has been generated because the screening was exited early.")
            
            partial_text = generate_partial_report(agent.state)
            st.markdown(f"""```\n{partial_text}\n```""")
            
            st.download_button(
                label="💾 Download Partial Screening Report",
                data=partial_text,
                file_name="oralguard_incomplete_report.txt",
                mime="text/plain",
                use_container_width=True
            )
            
        elif is_valid:
            if os.path.exists(SESSION_FILE):
                try:
                    os.remove(SESSION_FILE)
                except Exception:
                    pass
                    
            risk_level, reasons = assess_risk(agent.state)
            advice = get_recommended_advice(risk_level)
            
            if risk_level == "HIGH RISK":
                st.error("🔴 **HIGH RISK LEVEL DETECTED**")
            elif risk_level == "MEDIUM RISK":
                st.warning("🟡 **MEDIUM RISK LEVEL DETECTED**")
            else:
                st.success("🟢 **LOW RISK LEVEL DETECTED**")
                
            st.markdown(f"""
            ### Summary Metrics
            *   **Risk Level**: **{risk_level}**
            *   **Key Indicators**: {', '.join(reasons) if reasons else 'None'}
            
            ### Dr. Urja's Recommended Advice:
            {advice}
            """)
            
            with st.expander("ℹ️ Why this recommendation? (Clinical Reasoning)"):
                explanation = explain_recommendation(risk_level, reasons)
                st.markdown(explanation)
            
            st.markdown("---")
            st.markdown("### Patient Intake Dossier")
            
            report_html = f"""
            <div style="background-color: #0b1a20; padding: 20px; border-radius: 10px; border: 1px solid #11343f; font-family: monospace; font-size: 0.9rem; color: #a5c6d3;">
                ==================================================<br>
                📋  PATIENT SCREENING REPORT SUMMARY<br>
                ==================================================<br>
                👤 Patient Name & Age:  {agent.state['name']}, {agent.state['age']} years<br>
                🩹 Mouth Sores/Ulcers:  {"Yes - " + agent.state['sore_type'] + " (" + str(agent.state['sore_weeks']) + " weeks)" if agent.state['has_sores'] else "None"}<br>
                🚬 Tobacco/Gutka Use:   {"Yes - " + agent.state['tobacco_type'] + " (" + str(agent.state['tobacco_years']) + " years)" if agent.state['has_tobacco'] else "None"}<br>
                👅 Difficulty opening:  {"Yes (" + agent.state['swallow_detail'] + ")" if agent.state['diff_swallowing'] else "None"}<br>
                🩸 Pain/Bleeding/Lump:  {"Yes (" + agent.state['bleeding_detail'] + ")" if agent.state['has_bleeding_q'] else "None"}<br>
                --------------------------------------------------<br>
                ⚖️  Assessed Risk Level: {risk_level}<br>
                🔎 Key Risk Factors:    {', '.join(reasons) if reasons else 'No abnormal factors'}<br>
                --------------------------------------------------<br>
                🏥 Dr. Urja's Recommended Next Steps:<br>
                {advice}<br>
                ==================================================
            </div>
            """
            st.markdown(report_html, unsafe_allow_html=True)
            
            name_clean = agent.state['name'].replace(' ', '_')
            report_text = f"""==================================================
📋  PATIENT SCREENING REPORT SUMMARY
==================================================
👤 Patient Name & Age:  {agent.state['name']}, {agent.state['age']} years
🩹 Mouth Sores/Ulcers:  {"Yes - " + agent.state['sore_type'] + " (" + str(agent.state['sore_weeks']) + " weeks)" if agent.state['has_sores'] else "None"}
🚬 Tobacco/Gutka Use:   {"Yes - " + agent.state['tobacco_type'] + " (" + str(agent.state['tobacco_years']) + " years)" if agent.state['has_tobacco'] else "None"}
👅 Difficulty opening:  {"Yes (" + agent.state['swallow_detail'] + ")" if agent.state['diff_swallowing'] else "None"}
🩸 Pain/Bleeding/Lump:  {"Yes (" + agent.state['bleeding_detail'] + ")" if agent.state['has_bleeding_q'] else "None"}
--------------------------------------------------
⚖️  Assessed Risk Level: {risk_level}
🔎 Key Risk Factors:    {', '.join(reasons) if reasons else 'No abnormal factors'}
--------------------------------------------------
🏥 Dr. Urja's Recommended Next Steps:
{advice}
==================================================
"""
            st.download_button(
                label="💾 Download Screening Report",
                data=report_text,
                file_name=f"oralguard_report_{name_clean}.txt",
                mime="text/plain",
                use_container_width=True
            )
            
        else:
            st.info("Intake interview in progress. A complete report summary will appear here once the screening questions are fully completed.")
