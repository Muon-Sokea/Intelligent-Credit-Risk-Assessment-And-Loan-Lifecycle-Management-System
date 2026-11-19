import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from streamlit.testing.v1 import AppTest

from data.loan_applications_demo import create_loan_application_demo_data
from modules.loan_monitoring import (
    _report_pdf,
    _remaining_obligation,
    aging_bucket,
    allocate_payment,
    build_loan_overview,
    generate_repayment_schedule,
    is_disbursed_monitoring_account,
    _report_rows,
    schedule_status,
)

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _monitoring_record(application_id="APP-DISBURSED", account_status="Active"):
    today = date(2026, 4, 1)
    return {
        "application_id": application_id,
        "applicant_name": "Monitoring Test",
        "status": "Approved",
        "loan_monitoring": {
            "loan_account_id": f"LN-{application_id}",
            "disbursement": {
                "status": "Disbursed", "disbursed_at": date(2026, 1, 1),
                "disbursed_amount": 10000, "currency": "USD",
            },
            "account_status": account_status,
            "outstanding_balance": 7000 if account_status == "Active" else 0,
            "loan_type": "Personal Loan",
            "follow_up_required": True,
            "repayment_schedule": [
                {"due_date": today - timedelta(days=10), "amount_due": 500, "amount_paid": 200, "currency": "USD"},
                {"due_date": today + timedelta(days=10), "amount_due": 500, "amount_paid": 0, "currency": "USD"},
            ],
            "payments": [
                {"due_date": today - timedelta(days=20), "payment_date": (today - timedelta(days=20)).isoformat(), "amount_received": "100", "principal_allocation": "100", "interest_allocation": "0"},
                {"due_date": today - timedelta(days=10), "payment_date": (today - timedelta(days=8)).isoformat(), "amount_received": "200", "principal_allocation": "200", "interest_allocation": "0"},
            ],
            "activities": [
                {"event": "Payment recorded", "timestamp": "2026-03-24T10:00:00", "detail": "Installment received"},
                {"event": "Application submitted", "timestamp": "2026-03-23T10:00:00"},
            ],
        },
    }


class LoanMonitoringDataTests(unittest.TestCase):
    def test_incomplete_schedule_totals_are_unavailable_not_partial(self):
        record = _monitoring_record("APP-INCOMPLETE")
        record["loan_monitoring"]["repayment_schedule"][0].pop("amount_paid")
        self.assertIsNone(_remaining_obligation(record))

    def test_application_status_or_analyst_recommendation_is_not_disbursement(self):
        approved = {"application_id": "APP-APPROVED", "status": "Approved"}
        recommended = {"application_id": "APP-RECOMMENDED", "status": "Under Assessment", "latest_assessment_summary": {"recommendation": "Recommend Approval"}}
        false_disbursement = {"loan_monitoring": {"disbursement": {"status": "Approved", "disbursed_at": date(2026, 1, 1)}, "account_status": "Active"}}
        self.assertFalse(is_disbursed_monitoring_account(approved))
        self.assertFalse(is_disbursed_monitoring_account(recommended))
        self.assertFalse(is_disbursed_monitoring_account(false_disbursement))

    def test_overview_empty_state_does_not_invent_amounts_or_performance(self):
        records = create_loan_application_demo_data()
        summary = build_loan_overview(records, today=date(2026, 4, 1))
        self.assertEqual(summary["accounts"], [])
        self.assertEqual(len(summary["active"]), 0)
        self.assertEqual(len(summary["repaid"]), 0)
        self.assertIsNone(summary["disbursed_total"])
        self.assertIsNone(summary["outstanding_total"])
        self.assertIsNone(summary["on_time_rate"])
        self.assertIsNone(summary["late_rate"])
        self.assertIsNone(summary["total_received"])
        self.assertEqual(summary["activities"], [])

    def test_explicit_disbursements_schedule_and_payments_are_summarized(self):
        today = date(2026, 4, 1)
        active = _monitoring_record()
        repaid = _monitoring_record("APP-REPAID", "Fully Repaid")
        repaid_rows = generate_repayment_schedule(10000, 0, 12, "Monthly", date(2026, 3, 1), "USD")
        for row in repaid_rows:
            row["amount_paid"] = row["amount_due"]
            row["principal_paid"] = row["principal_due"]
            row["interest_paid"] = row["interest_due"]
        repaid["loan_monitoring"]["repayment_schedule"] = repaid_rows
        repaid["loan_monitoring"]["payments"] = [{"payment_date": "2026-03-31", "amount_received": "10000", "principal_allocation": "10000", "interest_allocation": "0"}]
        repaid["loan_monitoring"]["activities"] = []
        approved_only = {"application_id": "APP-NO-DISBURSEMENT", "status": "Approved", "loan_amount": 50000}
        summary = build_loan_overview([active, repaid, approved_only], today=today)
        self.assertEqual(len(summary["accounts"]), 2)
        self.assertEqual(len(summary["active"]), 1)
        self.assertEqual(len(summary["repaid"]), 1)
        self.assertEqual(summary["disbursed_total"], 20000)
        self.assertEqual(summary["outstanding_total"], 9700)
        self.assertEqual(summary["overdue_accounts"], ["LN-APP-DISBURSED"])
        self.assertEqual(summary["overdue_total"], 300)
        self.assertEqual(summary["max_dpd"], 10)
        self.assertEqual(summary["missed_installments"], 0)
        self.assertEqual(summary["on_time_rate"], 50)
        self.assertEqual(summary["late_rate"], 50)
        self.assertEqual(summary["total_received"], 10300)
        self.assertEqual(summary["followups"], ["APP-DISBURSED"])
        self.assertEqual([row["Activity"] for row in summary["activities"]], ["Payment recorded"])

    def test_incomplete_schedule_and_mixed_currency_totals_are_not_aggregated(self):
        first = _monitoring_record()
        first["loan_monitoring"]["repayment_schedule"][0].pop("amount_paid")
        second = _monitoring_record("APP-EUR")
        second["loan_monitoring"]["disbursement"]["currency"] = "EUR"
        summary = build_loan_overview([first, second], today=date(2026, 4, 1))
        self.assertIsNone(summary["disbursed_total"])
        self.assertIsNone(summary["outstanding_total"])
        self.assertIsNone(summary["overdue_accounts"])
        self.assertIsNone(summary["overdue_total"])
        self.assertIsNone(summary["missed_installments"])

    def test_unknown_payment_allocation_does_not_report_zero_principal_repayment(self):
        record = _monitoring_record()
        record["loan_monitoring"]["payments"] = [{"amount_received": "100", "payment_date": "2026-03-01"}]
        summary = build_loan_overview([record], today=date(2026, 4, 1))
        self.assertIsNone(summary["outstanding_total"])
        self.assertIsNone(summary["principal_repaid"])
        self.assertIsNone(summary["interest_received"])
        self.assertEqual(summary["total_received"], Decimal("100.00"))
        self.assertIsNone(summary["on_time_rate"])

    def test_reading_noneligible_application_does_not_add_monitoring_record(self):
        application = {"application_id": "APP-READ", "status": "Approved"}
        summary = build_loan_overview([application], today=date(2026, 4, 1))
        self.assertFalse(summary["accounts"])
        self.assertNotIn("loan_monitoring", application)

    def test_duplicate_account_or_application_ids_are_excluded_from_totals(self):
        first = _monitoring_record("APP-DUPLICATE")
        second = _monitoring_record("APP-DUPLICATE")
        second["applicant_name"] = "Duplicate copy"
        summary = build_loan_overview([first, second], today=date(2026, 4, 1))
        self.assertEqual(summary["accounts"], [])
        self.assertIsNone(summary["disbursed_total"])

    def test_schedule_amortization_zero_interest_and_quarterly_periods(self):
        monthly = generate_repayment_schedule(1000, 0, 12, "Monthly", date(2026, 1, 31), "USD")
        self.assertEqual(len(monthly), 12)
        self.assertEqual(monthly[0]["amount_due"], "83.33")
        self.assertEqual(monthly[-1]["principal_due"], "83.37")
        self.assertEqual(monthly[1]["due_date"], "2026-02-28")
        quarterly = generate_repayment_schedule(1200, 12, 12, "Quarterly", date(2026, 1, 15), "USD")
        self.assertEqual(len(quarterly), 4)
        self.assertEqual(quarterly[-1]["due_date"], "2026-10-15")
        self.assertEqual(sum(Decimal(row["principal_due"]) for row in quarterly), Decimal("1200.00"))
        with self.assertRaises(ValueError):
            generate_repayment_schedule(1200, 4, 10, "Quarterly", date(2026, 1, 15), "USD")

    def test_partial_payment_allocates_interest_then_principal_and_prevents_overpay(self):
        rows = generate_repayment_schedule(1000, 12, 12, "Monthly", date(2026, 2, 1), "USD")
        record = {"application_id": "APP-PAY", "loan_monitoring": {
            "loan_account_id": "LN-PAY", "account_status": "Active",
            "disbursement": {"status": "Disbursed", "disbursed_at": "2026-01-01", "disbursed_amount": "1000", "currency": "USD"},
            "repayment_schedule": rows, "payments": [], "activities": [],
        }}
        first_interest = Decimal(rows[0]["interest_due"])
        payment = allocate_payment(record, first_interest + Decimal("10.00"), date(2026, 2, 1))
        self.assertEqual(Decimal(payment["interest_allocation"]), first_interest)
        self.assertEqual(Decimal(payment["principal_allocation"]), Decimal("10.00"))
        self.assertEqual(Decimal(rows[0]["amount_paid"]), first_interest + Decimal("10.00"))
        self.assertEqual(len(record["loan_monitoring"]["payments"]), 1)
        with self.assertRaises(ValueError):
            allocate_payment(record, 100000, date(2026, 2, 1))

    def test_complete_payoff_updates_lifecycle_only_when_schedule_is_zero(self):
        rows = generate_repayment_schedule(1000, 0, 12, "Monthly", date(2026, 2, 1), "USD")
        record = {"application_id": "APP-PAID", "loan_monitoring": {
            "loan_account_id": "LN-PAID", "account_status": "Active",
            "disbursement": {"status": "Disbursed", "disbursed_at": "2026-01-01", "disbursed_amount": "1000", "currency": "USD"},
            "repayment_schedule": rows, "payments": [], "activities": [],
        }}
        total = sum(Decimal(row["amount_due"]) for row in rows)
        payment = allocate_payment(record, total, date.today())
        self.assertEqual(payment["principal_allocation"], "1000.00")
        self.assertEqual(record["loan_monitoring"]["account_status"], "Fully Repaid")
        self.assertEqual(build_loan_overview([record])["repaid"], [record])

    def test_dpd_status_aging_and_pdf_export(self):
        self.assertEqual(aging_bucket(0), "Current / Not Overdue")
        self.assertEqual(aging_bucket(30), "1–30 Days")
        self.assertEqual(aging_bucket(31), "31–60 Days")
        self.assertEqual(aging_bucket(61), "61–90 Days")
        self.assertEqual(aging_bucket(91), "More Than 90 Days")
        self.assertEqual(schedule_status({"due_date": "2026-03-01", "amount_due": 100, "amount_paid": 20}, date(2026, 4, 1)), "Overdue")
        self.assertTrue(_report_pdf(["Internal monitoring report"]).startswith(b"%PDF-1.4"))

    def test_report_filters_apply_to_accounts_and_aging(self):
        overdue = _monitoring_record("APP-OVERDUE")
        current = _monitoring_record("APP-CURRENT")
        current["loan_monitoring"]["loan_account_id"] = "LN-APP-CURRENT"
        current["loan_monitoring"]["repayment_schedule"] = [{"due_date": "2026-04-10", "amount_due": 100, "amount_paid": 0}]
        rows = _report_rows([overdue, current], date(2026, 4, 1), None, None, "Personal Loan", "All", "Active", "1–30 Days", "All")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Application ID"], "APP-OVERDUE")
        none = _report_rows([overdue, current], date(2026, 4, 1), date(2026, 5, 1), None, "All", "All", "All", "All", "All")
        self.assertEqual(none, [])


class LoanMonitoringPageTests(unittest.TestCase):
    def test_direct_monitoring_navigation_initializes_shared_applications_only(self):
        app = AppTest.from_file(str(APP_PATH))
        app.run()
        app.button(key="navigation-Loan Monitoring").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.session_state["loan_application_records"])
        self.assertTrue(any("Morgan Blake" in option for box in app.selectbox for option in box.options if "Approved application" in box.label))
        self.assertIn("No disbursed loan accounts are available", "\n".join(m.value for m in app.markdown))

    def test_navigation_overview_tabs_and_empty_state_render(self):
        record = create_loan_application_demo_data()[3]
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [record]
        app.run()
        self.assertEqual(app.session_state["active_page"], "Dashboard")
        app.button(key="navigation-Loan Monitoring").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["active_page"], "Loan Monitoring")
        self.assertEqual(app.button(key="navigation-Loan Monitoring").proto.type, "primary")
        self.assertEqual([tab.label for tab in app.get("tab")], [
            "Loan Overview", "Loan Accounts", "Repayment Schedule", "Overdue Monitoring", "Collection & Follow-up", "Monitoring Reports",
        ])
        rendered = "\n".join(item.value for item in app.markdown)
        self.assertIn("Loan Portfolio Monitoring", rendered)
        self.assertIn("No disbursed loan accounts are available", rendered)
        self.assertIn("do not qualify", rendered)
        self.assertIn("Not available", rendered)
        self.assertFalse(any("10000" in item.value for item in app.markdown))

    def test_dark_theme_and_report_workspace_render_without_errors(self):
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [_monitoring_record()]
        app.session_state["dark_mode"] = True
        app.run()
        app.button(key="navigation-Loan Monitoring").click().run()
        self.assertFalse(app.exception)
        style = "\n".join(item.value for item in app.markdown if "lm-title" in item.value)
        self.assertIn("#F1F5F9", style)
        rendered = "\n".join(item.value for item in app.markdown)
        self.assertIn("Export filtered report", rendered)
        downloads = {item.label for item in app.get("download_button")}
        self.assertIn("Download filtered CSV", downloads)
        self.assertIn("Download filtered Excel", downloads)
        self.assertIn("Download filtered PDF", downloads)

    def test_selected_loan_account_context_is_shared_between_tabs(self):
        first = _monitoring_record("APP-FIRST")
        second = _monitoring_record("APP-SECOND")
        second["loan_monitoring"]["loan_account_id"] = "LN-SECOND"
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [first, second]
        app.run()
        app.button(key="navigation-Loan Monitoring").click().run()
        app.selectbox(key="lm-account-detail-selector").select("LN-SECOND").run()
        self.assertEqual(app.session_state["loan_monitoring_selected_account"], "LN-SECOND")
        self.assertEqual(app.selectbox(key="lm-schedule-account-selector").value, "LN-SECOND")

    def test_eligible_account_renders_real_metrics_not_approved_application(self):
        eligible = _monitoring_record()
        approved_only = {"application_id": "APP-APPROVED", "applicant_name": "Approved Only", "status": "Approved", "loan_amount": 99000}
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [eligible, approved_only]
        app.run()
        app.button(key="navigation-Loan Monitoring").click().run()
        self.assertFalse(app.exception)
        rendered = "\n".join(item.value for item in app.markdown)
        self.assertIn("USD 10,000.00", rendered)
        self.assertIn("USD 9,700.00", rendered)
        self.assertNotIn("99,000", rendered)
        self.assertTrue(any("Payment recorded" in str(element.value) for element in app.dataframe))

    def test_staff_records_existing_disbursement_on_shared_approved_application(self):
        approved = next(r for r in create_loan_application_demo_data() if r.get("status") == "Approved")
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [approved]
        app.run()
        app.button(key="navigation-Loan Monitoring").click().run()
        app.text_input(key="lm-disbursement-decision-ref").set_value("EXT-DEC-2026-001")
        app.text_input(key="lm-disbursement-currency").set_value("USD")
        app.number_input(key="lm-disbursement-approved-amount").set_value(5000)
        app.number_input(key="lm-disbursement-actual-amount").set_value(4500)
        app.number_input(key="lm-disbursement-term").set_value(12)
        app.number_input(key="lm-disbursement-rate").set_value(0)
        app.selectbox(key="lm-disbursement-frequency").select("Monthly")
        app.date_input(key="lm-disbursement-date").set_value(date.today())
        app.date_input(key="lm-formal-decision-date").set_value(date.today())
        app.date_input(key="lm-first-repayment-date").set_value(date.today() + timedelta(days=31))
        app.checkbox(key="lm-disbursement-confirmation").check()
        app.button(key="FormSubmitter:lm-disbursement-form-Record disbursement and generate schedule").click().run()
        stored = app.session_state["loan_application_records"][0]
        self.assertFalse(app.exception)
        self.assertEqual(stored["application_id"], approved["application_id"])
        self.assertEqual(stored["loan_monitoring"]["disbursement"]["final_decision_reference"], "EXT-DEC-2026-001")
        self.assertEqual(stored["loan_monitoring"]["disbursement"]["disbursed_amount"], "4500.00")
        self.assertEqual(len(stored["loan_monitoring"]["repayment_schedule"]), 12)
        self.assertEqual(stored["final_lending_decision"]["status"], "Approved")
        self.assertEqual(stored.get("latest_assessment_summary"), approved.get("latest_assessment_summary"))

    def test_schedule_can_be_generated_for_existing_disbursed_account_and_survives_navigation(self):
        record = _monitoring_record("APP-SCHEDULE-REPAIR")
        record["loan_monitoring"]["repayment_schedule"] = []
        record["loan_monitoring"]["payments"] = []
        record["loan_monitoring"]["disbursement"].update({
            "annual_interest_rate": "0", "term_months": 12, "repayment_frequency": "Monthly",
            "first_repayment_date": (date.today() + timedelta(days=30)).isoformat(),
        })
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [record]
        app.run()
        app.button(key="navigation-Loan Monitoring").click().run()
        app.date_input(key="lm-existing-first-due-LN-APP-SCHEDULE-REPAIR").set_value(date.today() + timedelta(days=30))
        app.checkbox(key="lm-existing-confirm-LN-APP-SCHEDULE-REPAIR").check()
        app.button(key="FormSubmitter:lm-existing-schedule-form-LN-APP-SCHEDULE-REPAIR-Generate repayment schedule").click().run()
        saved = app.session_state["loan_application_records"][0]
        self.assertFalse(app.exception)
        self.assertEqual(len(saved["loan_monitoring"]["repayment_schedule"]), 12)
        self.assertEqual(saved["application_id"], "APP-SCHEDULE-REPAIR")
        self.assertEqual(saved["loan_monitoring"]["account_status"], "Active")
        app.button(key="navigation-Loan Applications").click().run()
        app.button(key="navigation-Loan Monitoring").click().run()
        self.assertEqual(len(app.session_state["loan_application_records"][0]["loan_monitoring"]["repayment_schedule"]), 12)
        self.assertFalse(app.exception)

    def test_payment_form_records_partial_payment_and_updates_principal(self):
        today = date.today()
        record = {
            "application_id": "APP-PAY-UI", "applicant_name": "Payment UI Test", "status": "Approved",
            "loan_monitoring": {
                "loan_account_id": "LN-PAY-UI", "account_status": "Active", "loan_type": "Personal Loan",
                "disbursement": {"status": "Disbursed", "disbursed_at": today.isoformat(), "disbursed_amount": "1000.00", "currency": "USD", "annual_interest_rate": "12", "term_months": 12, "repayment_frequency": "Monthly"},
                "repayment_schedule": generate_repayment_schedule(1000, 12, 12, "Monthly", today, "USD"),
                "payments": [], "activities": [], "collection_activities": [], "promises": [],
            },
        }
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [record]
        app.run()
        app.button(key="navigation-Loan Monitoring").click().run()
        app.number_input(key="lm-pay-amount-LN-PAY-UI").set_value(50)
        app.text_input(key="lm-pay-ref-LN-PAY-UI").set_value("TXN-UI-001")
        app.button(key="FormSubmitter:lm-payment-form-LN-PAY-UI-Record payment").click().run()
        saved = app.session_state["loan_application_records"][0]["loan_monitoring"]
        self.assertFalse(app.exception)
        self.assertEqual(len(saved["payments"]), 1)
        self.assertEqual(saved["payments"][0]["interest_allocation"], "10.00")
        self.assertEqual(saved["payments"][0]["principal_allocation"], "40.00")
        self.assertEqual(saved["outstanding_balance"], "960.00")
        self.assertEqual(saved["repayment_schedule"][0]["amount_paid"], "50.00")
        app.text_input(key="lm-pay-ref-LN-PAY-UI").set_value("TXN-UI-001")
        app.button(key="FormSubmitter:lm-payment-form-LN-PAY-UI-Record payment").click().run()
        saved = app.session_state["loan_application_records"][0]["loan_monitoring"]
        self.assertEqual(len(saved["payments"]), 1)
        self.assertTrue(any("already exists" in item.value for item in app.error))

    def test_collection_and_promise_forms_save_separate_history(self):
        record = _monitoring_record("APP-COLLECTION")
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [record]
        app.run()
        app.button(key="navigation-Loan Monitoring").click().run()
        app.text_area(key="lm-contact-response-LN-APP-COLLECTION").set_value("Borrower asked for a callback.")
        app.text_area(key="lm-contact-notes-LN-APP-COLLECTION").set_value("Discussed upcoming installment.")
        app.button(key="FormSubmitter:lm-collection-form-LN-APP-COLLECTION-Save collection activity").click().run()
        saved = app.session_state["loan_application_records"][0]["loan_monitoring"]
        self.assertFalse(app.exception)
        self.assertEqual(len(saved["collection_activities"]), 1)
        self.assertEqual(len(saved["payments"]), 2)
        app.number_input(key="lm-promise-amount-LN-APP-COLLECTION").set_value(125)
        app.text_input(key="lm-promise-notes-LN-APP-COLLECTION").set_value("Promise date confirmed by staff")
        app.button(key="FormSubmitter:lm-promise-form-LN-APP-COLLECTION-Save promise record").click().run()
        saved = app.session_state["loan_application_records"][0]["loan_monitoring"]
        self.assertFalse(app.exception)
        self.assertEqual(len(saved["promises"]), 1)
        self.assertEqual(saved["promises"][0]["status"], "Pending")
        self.assertEqual(len(saved["payments"]), 2)


if __name__ == "__main__":
    unittest.main()
