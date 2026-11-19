import csv
import io
import unittest
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest

from data.loan_applications_demo import create_loan_application_demo_data
from modules.loan_application import (
    build_application_export,
    filter_applications,
    generate_application_id,
    latest_risk_summary,
    summarize_applications,
    validate_application_form,
)


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class LoanApplicationLogicTests(unittest.TestCase):
    def setUp(self):
        self.records = create_loan_application_demo_data(date(2026, 1, 1))

    def test_search_filters_by_name_id_and_phone(self):
        self.assertEqual(
            [record["applicant_name"] for record in filter_applications(self.records, "Jordan")],
            ["Jordan Ellis"],
        )
        self.assertEqual(
            [record["application_id"] for record in filter_applications(self.records, "APP-DEMO-0003")],
            ["APP-DEMO-0003"],
        )
        self.assertEqual(
            [record["applicant_name"] for record in filter_applications(self.records, "0102")],
            ["Jordan Ellis"],
        )

    def test_status_purpose_date_filters_and_summary_counts(self):
        filtered = filter_applications(
            self.records,
            status="Under Review",
            purpose="Personal",
            date_range=(date(2025, 11, 1), date(2026, 1, 1)),
        )
        self.assertEqual([record["applicant_name"] for record in filtered], ["Riley Chen"])
        self.assertEqual(
            summarize_applications(self.records),
            {"total": 6, "pending_review": 3, "under_assessment": 1, "completed": 2},
        )
        self.records[0]["status"] = "Approved"
        self.assertEqual(
            summarize_applications(self.records),
            {"total": 6, "pending_review": 2, "under_assessment": 1, "completed": 3},
        )

    def test_latest_risk_summary_uses_newest_stored_result_without_calculation(self):
        record = {
            "risk_level": "Medium",
            "risk_assessments": [
                {"risk_level": "High", "assessed_at": "2026-05-01T09:00:00+00:00"},
                {"summary": "Low · demo assessment", "assessed_at": "2026-05-02T09:00:00+00:00"},
            ],
        }
        self.assertEqual(latest_risk_summary(record), "Low · demo assessment")
        self.assertEqual(latest_risk_summary({}), "Not Assessed")
        self.assertEqual(latest_risk_summary({"risk_level": "High"}), "High")

    def test_csv_and_excel_exports_follow_active_filters(self):
        filtered = filter_applications(
            self.records,
            query="Jordan",
            status="Under Review",
            purpose="Business",
            date_range=(date(2025, 12, 1), date(2025, 12, 31)),
        )
        csv_data = build_application_export(filtered, "csv")
        self.assertIsNotNone(csv_data)
        csv_rows = list(
            csv.DictReader(io.StringIO(csv_data.decode("utf-8-sig")))
        )
        self.assertEqual(len(csv_rows), 1)
        self.assertEqual(csv_rows[0]["Application ID"], "APP-DEMO-0002")
        self.assertEqual(csv_rows[0]["Applicant"], "Jordan Ellis")

        excel_data = build_application_export(filtered, "excel")
        self.assertIsNotNone(excel_data)
        worksheet = load_workbook(BytesIO(excel_data), read_only=True).active
        self.assertEqual(worksheet["A2"].value, "APP-DEMO-0002")
        self.assertEqual(worksheet["B2"].value, "Jordan Ellis")
        self.assertEqual(worksheet["C2"].value.date(), date(2025, 12, 26))
        self.assertIsNone(build_application_export([], "csv"))
        with self.assertRaises(ValueError):
            build_application_export(filtered, "pdf")

    def test_ids_increment_and_form_validation_rejects_bad_values(self):
        records = [*self.records, {"application_id": "APP-2026-0007"}]
        self.assertEqual(generate_application_id(records, date(2026, 1, 1)), "APP-2026-0008")
        self.assertEqual(generate_application_id(self.records, date(2026, 1, 1)), "APP-2026-0001")

        valid_values = {
            "full_name": "Demo Applicant",
            "date_of_birth": date(1990, 5, 15),
            "gender": "Prefer not to say",
            "phone": "+1 202 555 0199",
            "email": "demo@example.invalid",
            "address": "123 Demo Street",
            "employment_status": "Full-time",
            "occupation": "Analyst",
            "employer": "Demo Employer",
            "work_experience_years": 4,
            "monthly_income": 5000,
            "monthly_expenses": 1200,
            "existing_debt": 500,
            "other_obligations": 100,
            "loan_amount": 12000,
            "loan_purpose": "Personal",
            "loan_term_months": 36,
            "repayment_frequency": "Monthly",
        }
        self.assertEqual(validate_application_form(valid_values), [])
        valid_values.update(email="not-an-email", monthly_income=-1, loan_amount=-10)
        errors = validate_application_form(valid_values)
        self.assertIn("Enter a valid email address.", errors)
        self.assertIn("Monthly income cannot be negative.", errors)
        self.assertIn("Requested loan amount cannot be negative.", errors)


class LoanApplicationAppTests(unittest.TestCase):
    def test_management_header_exports_and_date_filter_are_present(self):
        app = AppTest.from_file(str(APP_PATH)).run()
        app.button(key="navigation-Loan Applications").click().run()

        rendered_markdown = "\n".join(item.value for item in app.markdown)
        self.assertIn("Application Management", rendered_markdown)
        self.assertIn(
            "Monitor application volume, status, and processing progress.",
            rendered_markdown,
        )
        self.assertEqual(
            {button.label for button in app.get("download_button")},
            {"Export CSV", "Export Excel"},
        )
        self.assertEqual(
            [date_input.label for date_input in app.date_input],
            ["Application date"],
        )

        app.text_input(key="loan_applications_search").set_value("no matching record").run()
        self.assertEqual(len(app.get("download_button")), 0)
        self.assertTrue(
            any("No matching applications to export." in item.value for item in app.info)
        )
        self.assertFalse(app.exception)

    def test_list_search_details_return_and_status_update(self):
        app = AppTest.from_file(str(APP_PATH)).run()
        app.button(key="navigation-Loan Applications").click().run()
        self.assertFalse(app.exception)
        button_keys = {button.key for button in app.button}
        self.assertIn("new-application", button_keys)
        self.assertNotIn("loan-applications-new-button", button_keys)
        self.assertEqual(sum(button.label == "New Application" for button in app.button), 1)
        self.assertFalse(
            any(
                '<h1 class="loan-page-title">Loan Applications</h1>' in item.value
                for item in app.markdown
            )
        )
        self.assertTrue(any("navbar-demo-badge" in item.value for item in app.markdown))
        self.assertEqual(sum(button.label == "View" for button in app.button), 6)

        app.text_input(key="loan_applications_search").set_value("Jordan").run()
        self.assertEqual(sum(button.label == "View" for button in app.button), 1)
        app.selectbox(key="loan_applications_status_filter").select("Under Review").run()
        app.selectbox(key="loan_applications_purpose_filter").select("Business").run()
        app.date_input(key="loan_applications_date_filter").set_value(
            (date.today() - timedelta(days=7), date.today())
        ).run()
        self.assertEqual(sum(button.label == "View" for button in app.button), 1)
        app.button(key="loan-applications-reset-filters").click().run()
        self.assertEqual(app.session_state["loan_applications_search"], "")
        self.assertEqual(app.session_state["loan_applications_status_filter"], "All")
        self.assertEqual(app.session_state["loan_applications_purpose_filter"], "All")
        dates = [record["application_date"] for record in app.session_state["loan_application_records"]]
        self.assertEqual(
            app.session_state["loan_applications_date_filter"],
            (min(dates), max(dates)),
        )
        self.assertEqual(sum(button.label == "View" for button in app.button), 6)
        app.text_input(key="loan_applications_search").set_value("Jordan").run()
        app.button(key="loan-id-APP-DEMO-0002").click().run()
        self.assertEqual(app.session_state["loan_application_view"], "details")
        self.assertEqual(app.session_state["loan_application_selected_id"], "APP-DEMO-0002")
        app.button(key="loan-detail-back").click().run()
        self.assertEqual(app.session_state["loan_applications_search"], "Jordan")

        app.button(key="loan-applications-reset-filters").click().run()
        app.button(key="loan-view-APP-DEMO-0001").click().run()
        app.selectbox(key="loan-status-APP-DEMO-0001").select("Under Assessment").run()
        app.button(key="loan-detail-update-status").click().run()
        record = next(
            item
            for item in app.session_state["loan_application_records"]
            if item["application_id"] == "APP-DEMO-0001"
        )
        self.assertEqual(record["status"], "Under Assessment")
        self.assertFalse(app.exception)

    def test_new_application_wizard_persists_and_submits(self):
        app = AppTest.from_file(str(APP_PATH)).run()
        app.button(key="new-application").click().run()
        self.assertEqual(app.session_state["active_page"], "Loan Applications")
        app.text_input(key="loan_form_full_name").set_value("Demo Applicant")
        app.date_input(key="loan_form_date_of_birth").set_value(date(1990, 5, 15))
        app.selectbox(key="loan_form_gender").select("Prefer not to say")
        app.text_input(key="loan_form_phone").set_value("+1 202 555 0199")
        app.text_input(key="loan_form_email").set_value("demo@example.invalid")
        app.text_area(key="loan_form_address").set_value("123 Demo Street")
        self._continue(app)

        app.selectbox(key="loan_form_employment_status").select("Full-time")
        app.text_input(key="loan_form_occupation").set_value("Analyst")
        app.number_input(key="loan_form_work_experience_years").set_value(4.0)
        app.text_input(key="loan_form_employer").set_value("Demo Employer")
        app.number_input(key="loan_form_monthly_income").set_value(5000.0)
        self._continue(app)

        app.number_input(key="loan_form_monthly_expenses").set_value(1200.0)
        app.number_input(key="loan_form_existing_debt").set_value(500.0)
        app.number_input(key="loan_form_other_obligations").set_value(100.0)
        self._continue(app)

        app.number_input(key="loan_form_loan_amount").set_value(12000.0)
        app.selectbox(key="loan_form_loan_purpose").select("Personal")
        app.number_input(key="loan_form_loan_term_months").set_value(36)
        app.selectbox(key="loan_form_repayment_frequency").select("Monthly")
        self._continue(app)

        self.assertEqual(app.session_state["loan_application_form_step"], 5)
        app.button(key="loan-form-submit").click().run()
        records = app.session_state["loan_application_records"]
        self.assertEqual(len(records), 7)
        self.assertEqual(records[0]["applicant_name"], "Demo Applicant")
        self.assertEqual(records[0]["status"], "Pending")
        self.assertTrue(records[0]["application_id"].startswith(f"APP-{date.today().year}-"))
        self.assertEqual(app.session_state["loan_application_view"], "list")
        self.assertIn(f"loan-view-{records[0]['application_id']}", {button.key for button in app.button})
        self.assertFalse(app.exception)

    def test_edit_application_saves_changes_without_changing_status(self):
        app = AppTest.from_file(str(APP_PATH)).run()
        app.button(key="navigation-Loan Applications").click().run()
        app.button(key="loan-view-APP-DEMO-0001").click().run()
        app.button(key="loan-detail-edit").click().run()
        app.text_input(key="loan_form_full_name").set_value("Edited Demo Applicant")
        for _ in range(4):
            self._continue(app)
        app.button(key="loan-form-submit").click().run()

        record = next(
            item
            for item in app.session_state["loan_application_records"]
            if item["application_id"] == "APP-DEMO-0001"
        )
        self.assertEqual(record["applicant_name"], "Edited Demo Applicant")
        self.assertEqual(record["status"], "Pending")
        self.assertEqual(app.session_state["loan_application_view"], "list")
        self.assertFalse(app.exception)

    def test_light_and_dark_theme_render_without_errors(self):
        app = AppTest.from_file(str(APP_PATH)).run()
        app.button(key="navigation-Loan Applications").click().run()
        app.button(key="theme-toggle").click().run()
        self.assertTrue(app.session_state["dark_mode"])
        self.assertFalse(app.exception)
        app.button(key="theme-toggle").click().run()
        self.assertFalse(app.session_state["dark_mode"])
        self.assertFalse(app.exception)

    @staticmethod
    def _continue(app):
        app.form_submit_button(
            key="FormSubmitter:loan-application-step-form-Continue"
        ).click().run()
        if app.exception:
            raise AssertionError(app.exception[0].message)
        if app.error:
            raise AssertionError(app.error[0].value)


if __name__ == "__main__":
    unittest.main()
