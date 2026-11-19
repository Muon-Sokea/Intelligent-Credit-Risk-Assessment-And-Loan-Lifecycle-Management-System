import unittest

from pathlib import Path

from streamlit.testing.v1 import AppTest

from data.loan_applications_demo import create_loan_application_demo_data
from modules.credit_assessment import (
    _application_search_filter,
    _financial_data,
    eligible_applications,
)


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class CreditAssessmentQueueTests(unittest.TestCase):
    def test_only_submitted_applications_enter_assessment_queue(self):
        records = create_loan_application_demo_data()
        queue = eligible_applications(records)
        self.assertEqual([record["application_id"] for record in queue], ["APP-DEMO-0003"])

        records[0]["submitted_for_assessment"] = True
        self.assertIn(records[0], eligible_applications(records))

    def test_search_and_filters_apply_only_to_the_submitted_queue(self):
        records = create_loan_application_demo_data()
        selected = _application_search_filter(records, "Casey", "Not Started", "Education")
        self.assertEqual([record["application_id"] for record in selected], ["APP-DEMO-0003"])
        self.assertEqual(_application_search_filter(records, "Taylor", "All", "All"), [])

    def test_financial_analysis_marks_missing_debt_and_rate_inputs_unavailable(self):
        record = create_loan_application_demo_data()[2]
        result = _financial_data(record)
        self.assertIsNone(result["dti"])
        self.assertIsNone(result["installment"])
        record.update(monthly_debt_payments=250, annual_interest_rate_percent=12)
        result = _financial_data(record)
        self.assertAlmostEqual(result["dti"], 250 / record["monthly_income"] * 100)
        self.assertGreater(result["installment"], 0)


class CreditAssessmentPageTests(unittest.TestCase):
    def setUp(self):
        self.app = AppTest.from_file(str(APP_PATH)).run()
        self.app.button(key="navigation-Credit Assessment").click().run()

    def test_workspace_has_six_sections_and_only_submitted_record(self):
        self.assertFalse(self.app.exception)
        self.assertEqual(
            [tab.label for tab in self.app.get("tab")],
            [
                "Assessment Overview",
                "Applicant & Documents",
                "Financial & Credit Analysis",
                "Credit Risk Assessment",
                "Findings & Recommendation",
                "Assessment History",
            ],
        )
        rendered = "\n".join(item.value for item in self.app.markdown)
        self.assertIn("Assessment Workspace", rendered)
        self.assertNotIn("<h1 class=\"ca-title\">Credit Assessment</h1>", rendered)
        selector = self.app.selectbox(key="credit_assessment_application_id")
        self.assertEqual(len(selector.options), 1)
        self.assertIn("APP-DEMO-0003", selector.options[0])
        self.assertEqual(selector.value, "APP-DEMO-0003")

    def test_document_verification_and_activity_persist_on_shared_record(self):
        key = "ca-document-APP-DEMO-0003-identification-document"
        self.app.selectbox(key=key).select("Verified").run()

        record = next(
            item
            for item in self.app.session_state["loan_application_records"]
            if item["application_id"] == "APP-DEMO-0003"
        )
        self.assertEqual(
            record["credit_assessment"]["documents"]["Identification document"]["status"],
            "Verified",
        )
        self.assertEqual(record["assessment_status"], "In Progress")
        self.assertTrue(
            any(event["event"] == "Document status changed" for event in record["credit_assessment"]["activity_history"])
        )
        self.assertFalse(self.app.exception)

    def test_recommendation_requires_justification_and_is_not_final_decision(self):
        record = next(
            item
            for item in self.app.session_state["loan_application_records"]
            if item["application_id"] == "APP-DEMO-0003"
        )
        recommendation_key = "ca-app-demo-0003-recommendation"
        submit_key = "FormSubmitter:ca-findings-form-app-demo-0003-Submit recommendation"
        justification_key = "ca-app-demo-0003-recommendation_justification"

        self.app.selectbox(key=recommendation_key).select("Recommend Approval")
        self.app.form_submit_button(key=submit_key).click().run()
        self.assertTrue(any("justification is required" in error.value for error in self.app.error))
        self.assertNotEqual(record["assessment_status"], "Completed")

        self.app.text_area(key=justification_key).set_value("Income and employment documents were reviewed for this demo assessment.")
        self.app.form_submit_button(key=submit_key).click().run()
        self.assertEqual(record["assessment_status"], "Completed")
        self.assertEqual(record["status"], "Under Assessment")
        self.assertEqual(record["credit_assessment"]["recommendation"], "Recommend Approval")
        self.assertEqual(record["latest_assessment_summary"]["recommendation"], "Recommend Approval")
        self.assertIn("not final lending decision", record["latest_assessment_summary"]["source"])
        self.assertTrue(any(event["event"] == "Assessment completed" for event in record["credit_assessment"]["activity_history"]))
        self.assertFalse(self.app.exception)

    def test_debt_analysis_handoff_uses_shared_application(self):
        self.app.button(key="ca-open-debt-analysis").click().run()
        self.assertEqual(self.app.session_state["active_page"], "Debt & Affordability")
        self.assertEqual(self.app.session_state["debt_analysis_application_id"], "APP-DEMO-0003")
        rendered = "\n".join(item.value for item in self.app.markdown)
        self.assertIn("Financial Analysis", rendered)
        self.assertFalse(self.app.exception)

    def test_dark_theme_renders_assessment_workspace(self):
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["dark_mode"] = True
        app.run()
        app.button(key="navigation-Credit Assessment").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("tab")), 6)


if __name__ == "__main__":
    unittest.main()
