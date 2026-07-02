import unittest
import os
from triage_engine import validate_inputs, assess_risk, get_recommended_advice, generate_partial_report, explain_recommendation
from agent import OralGuardAgent

class TestOralGuardTriage(unittest.TestCase):
    
    def setUp(self):
        self.temp_session_file = "temp_test_session.json"
        
    def tearDown(self):
        if os.path.exists(self.temp_session_file):
            try:
                os.remove(self.temp_session_file)
            except Exception:
                pass

    def test_validation_incomplete(self):
        """Test that validation fails and returns specific missing descriptions when details are empty."""
        empty_data = {
            "name": "",
            "age": 0,
            "has_sores": None,
            "has_tobacco": None,
            "diff_swallowing": None,
            "has_bleeding_q": None
        }
        is_valid, missing = validate_inputs(empty_data)
        self.assertFalse(is_valid)
        self.assertIn("patient name", missing)
        self.assertIn("valid patient age", missing)
        self.assertIn("whether you have mouth sores, ulcers, or patches recently", missing)
        self.assertIn("tobacco, pan masala, betel nut, or gutka usage status", missing)
        self.assertIn("difficulty swallowing or opening mouth status", missing)
        self.assertIn("pain, burning sensation, or unexplained bleeding status", missing)

    def test_validation_missing_sore_details(self):
        """Test that validation fails when has_sores is True but details are missing."""
        incomplete_sores = {
            "name": "Jane Doe",
            "age": 45,
            "has_sores": True,
            "sore_type": "",  # missing
            "sore_weeks": -1,  # missing
            "has_tobacco": False,
            "diff_swallowing": False,
            "has_bleeding_q": False
        }
        is_valid, missing = validate_inputs(incomplete_sores)
        self.assertFalse(is_valid)
        self.assertIn("specific type of sore (sores, ulcers, or patches)", missing)
        self.assertIn("duration of mouth sores/ulcers (in weeks)", missing)

    def test_validation_complete(self):
        """Test that validation passes when all required fields are filled."""
        complete_data = {
            "name": "Jane Doe",
            "age": 45,
            "has_sores": True,
            "sore_type": "ulcer",
            "sore_weeks": 2,
            "has_tobacco": True,
            "tobacco_type": "cigarettes",
            "tobacco_years": 4,
            "diff_swallowing": True,
            "swallow_detail": "difficulty swallowing",
            "swallow_duration": "3 weeks",
            "has_bleeding_q": True,
            "bleeding_detail": "burning sensation on tongue for 1 week"
        }
        is_valid, missing = validate_inputs(complete_data)
        self.assertTrue(is_valid)
        self.assertEqual(len(missing), 0)

    def test_low_risk(self):
        """Test classification of Low Risk patients (no risk factors, short sore duration)."""
        low_risk_data = {
            "has_sores": True,
            "sore_type": "sore",
            "sore_weeks": 1,
            "has_tobacco": False,
            "diff_swallowing": False,
            "has_bleeding_q": False
        }
        risk, reasons = assess_risk(low_risk_data)
        self.assertEqual(risk, "LOW RISK")
        self.assertIn("a mouth sore present for less than 2 weeks with no other risk factors", reasons)

    def test_medium_risk_tobacco(self):
        """Test classification of Medium Risk due to tobacco use <= 5 years."""
        med_risk_data = {
            "has_sores": False,
            "has_tobacco": True,
            "tobacco_type": "gutka",
            "tobacco_years": 3,
            "diff_swallowing": False,
            "has_bleeding_q": False
        }
        risk, reasons = assess_risk(med_risk_data)
        self.assertEqual(risk, "MEDIUM RISK")
        self.assertIn("tobacco/gutka/betel nut use under 5 years", reasons)

    def test_high_risk_long_sores(self):
        """Test classification of High Risk due to mouth sore duration > 4 weeks."""
        high_risk_data = {
            "has_sores": True,
            "sore_type": "ulcer",
            "sore_weeks": 5,
            "has_tobacco": False,
            "diff_swallowing": False,
            "has_bleeding_q": False
        }
        risk, reasons = assess_risk(high_risk_data)
        self.assertEqual(risk, "HIGH RISK")
        self.assertIn("a mouth sore/ulcer present for more than 4 weeks", reasons)

    def test_high_risk_patches(self):
        """Test classification of High Risk due to presence of red/white patches."""
        high_risk_data = {
            "has_sores": True,
            "sore_type": "white patches on inner cheek",
            "sore_weeks": 1,
            "has_tobacco": False,
            "diff_swallowing": False,
            "has_bleeding_q": False
        }
        risk, reasons = assess_risk(high_risk_data)
        self.assertEqual(risk, "HIGH RISK")
        self.assertIn("white or red patches in the mouth", reasons)

    def test_partial_report_rendering(self):
        """Test that partial reports are rendered correctly with missing parameters and no risk level."""
        partial_data = {
            "name": "Jane",
            "age": 30,
            "has_sores": True,
            "sore_type": "ulcer",
            "sore_weeks": -1,
            "has_tobacco": False,
            "diff_swallowing": None,
            "has_bleeding_q": None
        }
        report = generate_partial_report(partial_data)
        self.assertIn("INCOMPLETE SCREENING DOSSIER", report)
        self.assertIn("Patient: Jane, 30 years", report)
        self.assertIn("Duration of mouth sores", report)
        self.assertIn("Difficulty swallowing or opening mouth wide status", report)
        self.assertIn("Pain, burning, or unexplained bleeding status", report)
        self.assertNotIn("Assessed Risk Level", report)

    def test_recommendation_explanations(self):
        """Test evidence-based clinical reasoning recommendations."""
        high_risk_reasons = ["a mouth sore/ulcer present for more than 4 weeks", "difficulty swallowing"]
        explanation = explain_recommendation("HIGH RISK", high_risk_reasons)
        self.assertIn("assessed this patient as HIGH RISK", explanation)
        self.assertIn("lesions (>4 weeks) or leukoplakia/erythroplakia", explanation)
        self.assertIn("immediate referral to an oral surgeon", explanation)

        low_risk_reasons = ["no history of tobacco use"]
        low_explanation = explain_recommendation("LOW RISK", low_risk_reasons)
        self.assertIn("routine biannual dental examinations", low_explanation)

    def test_agent_serialization(self):
        """Test saving and restoring screening agent session variables."""
        agent = OralGuardAgent(use_offline=True)
        agent.state["name"] = "Alice"
        agent.state["age"] = 50
        agent.state["has_sores"] = False
        agent.offline_step = 4
        agent.add_message("model", "Question...")
        agent.add_message("user", "Answer...")
        
        agent.save_session(self.temp_session_file)
        self.assertTrue(os.path.exists(self.temp_session_file))
        
        restored = OralGuardAgent(use_offline=True)
        restored.load_session(self.temp_session_file)
        
        self.assertEqual(restored.state["name"], "Alice")
        self.assertEqual(restored.state["age"], 50)
        self.assertEqual(restored.state["has_sores"], False)
        self.assertEqual(restored.offline_step, 4)
        self.assertEqual(len(restored.history), 2)
        self.assertEqual(restored.history[0]["role"], "model")
        self.assertEqual(restored.history[1]["role"], "user")

if __name__ == "__main__":
    unittest.main()
