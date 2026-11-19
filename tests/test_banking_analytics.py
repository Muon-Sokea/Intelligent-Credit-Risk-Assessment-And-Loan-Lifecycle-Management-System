import unittest
from datetime import date, timedelta
from pathlib import Path

from streamlit.testing.v1 import AppTest

from data.loan_applications_demo import create_loan_application_demo_data
from modules.banking_analytics import (
    _app_frame,
    _dedupe_applications,
    _period_metrics,
    calculate_par,
)
from modules.loan_monitoring import generate_repayment_schedule

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _account():
    today = date.today()
    first_due = today - timedelta(days=40)
    schedule = generate_repayment_schedule(1000, 0, 2, "Monthly", first_due, "USD")
    schedule[0]["amount_paid"] = "100.00"
    schedule[0]["principal_paid"] = "100.00"
    record = {
        "application_id": "APP-BA-001",
        "applicant_name": "Private Example",
        "borrower_type": "Personal",
        "loan_amount": 1500,
        "loan_purpose": "Home",
        "application_date": today,
        "status": "Approved",
        "final_lending_decision": {"status": "Approved", "decision_reference": "EXT-001"},
        "risk_level": "High",
        "loan_monitoring": {
            "loan_account_id": "LN-BA-001",
            "account_status": "Active",
            "loan_type": "Personal Loan",
            "disbursement": {"status": "Disbursed", "disbursed_at": today - timedelta(days=90), "disbursed_amount": "1000.00", "currency": "USD"},
            "repayment_schedule": schedule,
            "payments": [{"payment_date": today - timedelta(days=35), "due_date": first_due.isoformat(), "amount_received": "100.00", "principal_allocation": "100.00", "interest_allocation": "0.00", "currency": "USD"}],
        },
    }
    return record


class BankingAnalyticsCalculationTests(unittest.TestCase):
    def test_application_records_are_deduplicated_by_id(self):
        one = {"application_id": "APP-1", "loan_amount": 100}
        duplicate = {"application_id": "APP-1", "loan_amount": 900}
        no_id_a, no_id_b = {"loan_amount": 5}, {"loan_amount": 10}
        result = _dedupe_applications([one, duplicate, no_id_a, no_id_b])
        self.assertEqual(result, [one, no_id_a, no_id_b])

    def test_application_decision_and_actual_portfolio_values_use_distinct_sources(self):
        record = _account()
        frame = _app_frame([record])
        self.assertEqual(frame.loc[0, "Final Decision"], "Approved")
        record.pop("final_lending_decision")
        frame = _app_frame([record])
        self.assertEqual(frame.loc[0, "Final Decision"], "Not recorded")

    def test_period_metrics_use_actual_disbursement_and_recorded_repayments(self):
        record = _account()
        metrics = _period_metrics([record], [record], None, None)
        self.assertEqual(metrics["overview"]["outstanding_total"], 900)
        self.assertEqual(metrics["disbursement_overview"]["disbursed_total"], 1000)
        self.assertEqual(metrics["received"], 100)
        self.assertEqual(metrics["principal"], 100)
        self.assertEqual(metrics["interest"], 0)
        current_day_only = _period_metrics([record], [record], date.today(), date.today())
        self.assertIsNone(current_day_only["disbursement_overview"]["disbursed_total"])
        self.assertEqual(current_day_only["overview"]["outstanding_total"], 900)
        self.assertIsNone(current_day_only["average_requested"])

    def test_par_counts_unique_outstanding_balance_once_and_uses_dpd_cutoffs(self):
        record = _account()
        self.assertEqual(calculate_par([record], date.today(), 30), 100.0)
        self.assertEqual(calculate_par([record], date.today(), 60), 0.0)
        self.assertEqual(calculate_par([record], date.today(), 90), 0.0)

    def test_par_is_unavailable_with_incomplete_schedule_or_mixed_currency(self):
        record = _account()
        record["loan_monitoring"]["repayment_schedule"][0].pop("amount_paid")
        self.assertIsNone(calculate_par([record], date.today(), 30))
        record = _account()
        second = _account()
        second["application_id"] = "APP-BA-002"
        second["loan_monitoring"]["loan_account_id"] = "LN-BA-002"
        second["loan_monitoring"]["disbursement"]["currency"] = "EUR"
        self.assertIsNone(calculate_par([record, second], date.today(), 30))


class BankingAnalyticsPageTests(unittest.TestCase):
    def test_six_tabs_render_and_exports_build_without_mutating_records(self):
        record = _account()
        original = repr(record)
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [record]
        app.run()
        app.button(key="navigation-Banking Analytics").click().run()
        self.assertFalse(app.exception)
        self.assertEqual([tab.label for tab in app.get("tab")], [
            "Portfolio Overview", "Loan Portfolio Analysis", "Credit Risk Analytics",
            "Repayment & Delinquency Analytics", "Customer & Borrower Analytics",
            "Financial Performance & Reports",
        ])
        labels = [button.label for button in app.get("download_button")]
        self.assertIn("Download filtered CSV", labels)
        self.assertIn("Download filtered Excel", labels)
        self.assertIn("Download filtered PDF", labels)
        export_urls = {button.label: button.proto.url for button in app.get("download_button")}
        self.assertTrue(export_urls["Download filtered CSV"].endswith(".csv"))
        self.assertTrue(export_urls["Download filtered Excel"].endswith(".xlsx"))
        self.assertTrue(export_urls["Download filtered PDF"].endswith(".pdf"))
        self.assertEqual(repr(app.session_state["loan_application_records"][0]), original)

    def test_global_filter_reset_and_empty_state(self):
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = create_loan_application_demo_data()
        app.run()
        app.button(key="navigation-Banking Analytics").click().run()
        app.selectbox(key="ba-borrower").select("Personal").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("No applications match" in item.value for item in app.info))
        app.button(key="ba-reset-filters").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="ba-borrower").value, "All")

    def test_custom_reporting_period_validates_and_renders(self):
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = create_loan_application_demo_data()
        app.run()
        app.button(key="navigation-Banking Analytics").click().run()
        app.selectbox(key="ba-period").select("Custom Date Range").run()
        app.date_input(key="ba-custom-period").set_value((date.today() - timedelta(days=10), date.today())).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="ba-period").value, "Custom Date Range")

    def test_direct_navigation_initializes_existing_shared_application_demo(self):
        app = AppTest.from_file(str(APP_PATH))
        app.run()
        app.button(key="navigation-Banking Analytics").click().run()
        self.assertFalse(app.exception)
        self.assertGreater(len(app.session_state["loan_application_records"]), 0)
        self.assertTrue(any("No eligible disbursed loan records" in item.value for item in app.info))


if __name__ == "__main__":
    unittest.main()
