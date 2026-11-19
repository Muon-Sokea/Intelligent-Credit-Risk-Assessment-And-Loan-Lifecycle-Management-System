import unittest

from pathlib import Path

from streamlit.testing.v1 import AppTest

from data.loan_applications_demo import create_loan_application_demo_data
from modules.debt_analysis import (
    BUSINESS_EXPENSE_CATEGORIES,
    BUSINESS_OBLIGATION_EXPENSE_CATEGORIES,
    PERSONAL_EXPENSE_CATEGORIES,
    PERSONAL_DEBT_TYPES,
    BUSINESS_DEBT_TYPES,
    _borrower_type,
    _financial_analysis_data,
    _information_state,
    build_financial_report_data,
    business_monthly_operating_income,
    calculate_amortizing_loan,
    calculate_business_cfads,
    calculate_business_capacity,
    calculate_obligations_summary,
    calculate_personal_capacity,
    normalize_monthly_amount,
    personal_monthly_income,
    simulate_business_scenario,
    simulate_personal_scenario,
    _financial_report_csv,
    _financial_report_lines,
    _financial_report_pdf,
)


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class DebtAnalysisDataTests(unittest.TestCase):
    def test_income_frequencies_normalize_to_monthly_transparently(self):
        self.assertEqual(normalize_monthly_amount(1200, "Monthly"), 1200)
        self.assertAlmostEqual(normalize_monthly_amount(1200, "Weekly"), 5200)
        self.assertAlmostEqual(normalize_monthly_amount(1200, "Biweekly"), 2600)
        self.assertEqual(normalize_monthly_amount(1200, "Annual"), 100)
        self.assertIsNone(normalize_monthly_amount(1200, "Unknown"))
        self.assertIsNone(normalize_monthly_amount(-1, "Monthly"))

    def test_part_two_analysis_inputs_are_separate_from_original_application_fields(self):
        record = {"monthly_income": 3600}
        analysis = _financial_analysis_data(record)
        analysis["income_sources"].append({"name": "Salary", "gross_amount": 5000, "frequency": "Monthly"})
        self.assertEqual(record["monthly_income"], 3600)
        self.assertEqual(record["financial_analysis"]["income_cash_flow"]["income_sources"][0]["name"], "Salary")

    def test_business_cfads_requires_complete_periodized_inputs(self):
        complete = calculate_business_cfads(
            20000, 1000, [1000] * len(BUSINESS_EXPENSE_CATEGORIES),
            expense_categories_complete=True, other_income_reviewed=True, currency_confirmed=True,
        )
        self.assertEqual(complete, 13000)
        self.assertIsNone(calculate_business_cfads(
            20000, 1000, [1000], expense_categories_complete=False,
            other_income_reviewed=True, currency_confirmed=True,
        ))
        self.assertIsNone(calculate_business_cfads(
            20000, None, [1000] * len(BUSINESS_EXPENSE_CATEGORIES),
            expense_categories_complete=True, other_income_reviewed=False, currency_confirmed=True,
        ))

    def test_personal_obligations_total_normalizes_and_uses_adjustment_once(self):
        expenses = [
            {"category": category, "amount": 100, "frequency": "Monthly", "entry_source": "Applicant-declared"}
            for category in PERSONAL_EXPENSE_CATEGORIES
        ]
        expenses.append({"category": PERSONAL_EXPENSE_CATEGORIES[0], "amount": 200, "frequency": "Monthly", "entry_source": "Staff adjustment"})
        debts = [
            {"debt_identity": "loan-1", "debt_type": PERSONAL_DEBT_TYPES[0], "outstanding_balance": 5000,
             "monthly_payment": 100, "payment_frequency": "Monthly", "entry_source": "Applicant-declared"},
            {"debt_identity": "loan-1", "debt_type": PERSONAL_DEBT_TYPES[0], "outstanding_balance": 4500,
             "monthly_payment": 120, "payment_frequency": "Monthly", "entry_source": "Staff adjustment"},
        ]
        result = calculate_obligations_summary(expenses, debts, PERSONAL_EXPENSE_CATEGORIES, currency_confirmed=True)
        self.assertEqual(result["total_expenses"], 800)
        self.assertEqual(result["total_monthly_debt_payments"], 120)
        self.assertEqual(result["total_outstanding_debt"], 4500)

    def test_missing_expense_differs_from_zero_and_confirmed_no_debt(self):
        zero_entry = [{"category": PERSONAL_EXPENSE_CATEGORIES[0], "amount": 0, "frequency": "Monthly", "entry_source": "Applicant-declared"}]
        incomplete = calculate_obligations_summary(zero_entry, [], PERSONAL_EXPENSE_CATEGORIES, currency_confirmed=True)
        self.assertEqual(incomplete["expense_subtotal"], 0)
        self.assertIsNone(incomplete["total_expenses"])
        self.assertIn(PERSONAL_EXPENSE_CATEGORIES[1], incomplete["missing_expense_categories"])
        self.assertIsNone(incomplete["total_monthly_debt_payments"])
        complete_none = calculate_obligations_summary([], [], PERSONAL_EXPENSE_CATEGORIES, currency_confirmed=True, no_debts_reported=True)
        self.assertEqual(complete_none["total_monthly_debt_payments"], 0)
        self.assertEqual(complete_none["total_outstanding_debt"], 0)

    def test_business_obligations_reuse_part_two_operating_expenses(self):
        part_two_expenses = [
            {"category": category, "amount": 100, "frequency": "Monthly", "verification_status": "Unverified"}
            for category in BUSINESS_EXPENSE_CATEGORIES
        ]
        adjustment = [{"category": BUSINESS_OBLIGATION_EXPENSE_CATEGORIES[0], "amount": 250, "frequency": "Monthly", "entry_source": "Staff adjustment"}]
        result = calculate_obligations_summary(adjustment, [], BUSINESS_OBLIGATION_EXPENSE_CATEGORIES, currency_confirmed=True, no_debts_reported=True, part_two_business_expenses=part_two_expenses)
        self.assertEqual(result["total_expenses"], 950)
        self.assertEqual(result["active_expenses"][BUSINESS_OBLIGATION_EXPENSE_CATEGORIES[0]]["amount"], 250)

    def test_business_debt_balance_and_monthly_service_are_separate(self):
        debt = {"debt_identity": "business-loan-1", "debt_type": BUSINESS_DEBT_TYPES[0],
                "outstanding_balance": 24000, "monthly_payment": 1200, "payment_frequency": "Monthly",
                "entry_source": "Applicant-declared"}
        result = calculate_obligations_summary([], [debt], BUSINESS_EXPENSE_CATEGORIES, currency_confirmed=True, no_debts_reported=False)
        self.assertEqual(result["total_outstanding_debt"], 24000)
        self.assertEqual(result["total_monthly_debt_payments"], 1200)

    def test_amortization_supports_zero_interest_and_payment_frequencies(self):
        zero_rate = calculate_amortizing_loan(12000, 0, 12, "Monthly")
        self.assertEqual(zero_rate["installment"], 1000)
        self.assertEqual(zero_rate["total_repayment"], 12000)
        self.assertEqual(zero_rate["total_interest"], 0)
        biweekly = calculate_amortizing_loan(12000, 12, 12, "Biweekly")
        self.assertEqual(biweekly["periods"], 26)
        self.assertAlmostEqual(biweekly["monthly_installment"], biweekly["installment"] * 26 / 12)
        self.assertIsNone(calculate_amortizing_loan(12000, None, 12, "Monthly"))

    def test_personal_capacity_formulas_and_zero_denominator(self):
        result = calculate_personal_capacity(5000, 4000, 1500, 500, 1000)
        self.assertEqual(result["dti_percent"], 10)
        self.assertEqual(result["dsti_percent"], 30)
        self.assertEqual(result["disposable_income"], 2000)
        self.assertEqual(result["remaining_income"], 1000)
        zero_income = calculate_personal_capacity(0, 4000, 1500, 500, 1000)
        self.assertIsNone(zero_income["dti_percent"])
        self.assertIsNone(zero_income["dsti_percent"])

    def test_business_capacity_uses_monthly_debt_service_period(self):
        result = calculate_business_capacity(13000, 1500, 1000)
        self.assertEqual(result["total_monthly_debt_service"], 2500)
        self.assertEqual(result["dscr"], 5.2)
        self.assertEqual(result["remaining_cash_flow"], 10500)
        zero_service = calculate_business_capacity(13000, 0, 0)
        self.assertIsNone(zero_service["dscr"])
        self.assertEqual(zero_service["remaining_cash_flow"], 13000)
        negative_cash_flow = calculate_business_capacity(-500, 100, 100)
        self.assertEqual(negative_cash_flow["dscr"], -2.5)
        self.assertEqual(negative_cash_flow["remaining_cash_flow"], -700)

    def test_personal_scenario_stress_recalculates_capacity_and_zero_rate(self):
        source = {"loan_amount": 12000, "annual_interest_rate": 0, "loan_term_months": 12}
        result = simulate_personal_scenario(
            gross_monthly_income=5000, net_monthly_income=4000, monthly_living_expenses=1500,
            existing_monthly_debt_payments=500, loan_amount=12000, annual_interest_rate=0,
            loan_term_months=12, repayment_frequency="Monthly", income_reduction_percent=20,
            living_expense_increase_percent=10, existing_debt_increase_percent=20,
        )
        self.assertEqual(result["gross_monthly_income"], 4000)
        self.assertEqual(result["net_monthly_income"], 3200)
        self.assertAlmostEqual(result["monthly_living_expenses"], 1650)
        self.assertEqual(result["existing_monthly_debt_payments"], 600)
        self.assertEqual(result["loan_calculation"]["monthly_installment"], 1000)
        self.assertAlmostEqual(result["dti_percent"], 15)
        self.assertEqual(source["annual_interest_rate"], 0)

    def test_business_scenario_uses_revenue_less_costs_and_debt_service(self):
        result = simulate_business_scenario(
            monthly_revenue=20000, monthly_other_operating_income=1000, monthly_operating_expenses=8000,
            existing_monthly_debt_service=1500, loan_amount=12000, annual_interest_rate=0,
            loan_term_months=12, repayment_frequency="Monthly", revenue_reduction_percent=25,
            operating_expense_increase_percent=10, existing_debt_service_increase_percent=20,
        )
        self.assertEqual(result["monthly_revenue"], 15000)
        self.assertEqual(result["cfads"], 15000 + 1000 - 8800)
        self.assertEqual(result["existing_monthly_debt_service"], 1800)
        self.assertEqual(result["total_monthly_debt_service"], 2800)
        self.assertAlmostEqual(result["dscr"], 7200 / 2800)
        self.assertEqual(result["remaining_cash_flow"], 7200 - 2800)

    def test_scenario_missing_values_and_extreme_stress_are_safe(self):
        personal = simulate_personal_scenario(
            gross_monthly_income=0, net_monthly_income=None, monthly_living_expenses=None,
            existing_monthly_debt_payments=None, loan_amount=1_000_000, annual_interest_rate=1000,
            loan_term_months=1, repayment_frequency="Monthly", income_reduction_percent=100,
        )
        self.assertIsNone(personal["dti_percent"])
        self.assertIsNone(personal["remaining_income"])
        self.assertEqual(personal["gross_monthly_income"], 0)
        business = simulate_business_scenario(
            monthly_revenue=None, monthly_other_operating_income=None, monthly_operating_expenses=None,
            existing_monthly_debt_service=None, loan_amount=1_000_000, annual_interest_rate=1000,
            loan_term_months=1, repayment_frequency="Monthly", revenue_reduction_percent=100,
            operating_expense_increase_percent=1000,
        )
        self.assertIsNone(business["cfads"])
        self.assertIsNone(business["dscr"])
        self.assertIsNone(business["remaining_cash_flow"])
        with self.assertRaises(ValueError):
            simulate_personal_scenario(
                gross_monthly_income=1, net_monthly_income=1, monthly_living_expenses=1,
                existing_monthly_debt_payments=1, loan_amount=100, annual_interest_rate=1,
                loan_term_months=12, repayment_frequency="Monthly", income_reduction_percent=-1,
            )

    def test_personal_report_uses_normalized_sources_and_capacity_metrics(self):
        record = {
            "borrower_type": "Personal", "applicant_name": "Report Applicant", "loan_amount": 12000,
            "loan_purpose": "Personal", "status": "Under Assessment",
            "financial_analysis": {
                "income_cash_flow": {"currency": "USD", "currency_confirmed": True, "income_sources": [
                    {"name": "Salary", "type": "Employment", "gross_amount": 6000, "net_amount": 5000, "frequency": "Monthly", "verification_status": "Verified"},
                ]},
                "obligations": {
                    "personal_living_expenses": [{"category": category, "amount": 100, "frequency": "Monthly", "entry_source": "Applicant-declared"} for category in PERSONAL_EXPENSE_CATEGORIES],
                    "personal_debts": [], "personal_no_debts_reported": True,
                },
                "repayment_capacity": {
                    "calculator": {"currency": "USD", "loan_amount": 12000, "annual_interest_rate": 0, "loan_term_months": 12, "repayment_frequency": "Monthly", "monthly_installment": 1000, "total_repayment": 12000, "total_interest": 0},
                    "personal": {"gross_monthly_income": 6000, "net_monthly_income": 5000, "monthly_living_expenses": 700, "existing_monthly_debt_payments": 0, "dti_percent": 0, "dsti_percent": 16.6667, "disposable_income": 4300, "remaining_income": 3300, "interpretation": "Not assessed — bank policy not configured"},
                },
            },
        }
        report = build_financial_report_data(record, "APP-PERSONAL-1")
        self.assertEqual(report["borrower_type"], "Personal")
        self.assertEqual(report["income_rows"][0]["Monthly gross"], 6000)
        self.assertEqual(report["expense_rows"][0]["Normalized monthly amount"], 100)
        self.assertEqual(report["debt_rows"], [])
        self.assertEqual(report["sections"][3]["rows"][-2][1], 3300)
        self.assertTrue(report["currency_confirmed"])

    def test_business_report_reuses_monthly_cfads_and_separates_obligations(self):
        from modules.debt_analysis import BUSINESS_OBLIGATION_EXPENSE_CATEGORIES
        record = {
            "borrower_type": "Business", "business_name": "Report Trading Ltd", "business_type": "Retail",
            "industry": "Retail", "loan_amount": 50000, "loan_purpose": "Business", "status": "Submitted",
            "financial_analysis": {
                "income_cash_flow": {"currency": "USD", "currency_confirmed": True, "other_operating_income_reviewed": True, "income_sources": [
                    {"name": "Sales", "type": "Business revenue", "gross_amount": 30000, "frequency": "Monthly"},
                    {"name": "Other income", "type": "Other operating income", "gross_amount": 1000, "frequency": "Monthly"},
                ], "business_expenses": []},
                "obligations": {
                    "business_operating_expenses": [{"category": category, "amount": 1000, "frequency": "Monthly", "entry_source": "Applicant-declared"} for category in BUSINESS_OBLIGATION_EXPENSE_CATEGORIES],
                    "business_debts": [{"debt_identity": "debt-1", "debt_type": BUSINESS_DEBT_TYPES[0], "lender": "Lender A", "outstanding_balance": 12000, "monthly_payment": 600, "payment_frequency": "Monthly", "entry_source": "Applicant-declared"}],
                },
                "repayment_capacity": {
                    "calculator": {"currency": "USD", "loan_amount": 50000, "annual_interest_rate": 6, "loan_term_months": 60, "repayment_frequency": "Monthly", "monthly_installment": 966.64, "total_repayment": 57998, "total_interest": 7998},
                    "business": {"monthly_business_revenue": 30000, "monthly_other_operating_income": 1000, "cfads": 23000, "existing_monthly_debt_service": 600, "proposed_monthly_installment": 966.64, "total_monthly_debt_service": 1566.64, "dscr": 14.68, "remaining_cash_flow": 21433.36, "interpretation": "Requires Further Review"},
                },
            },
        }
        report = build_financial_report_data(record, "APP-BUSINESS-1")
        self.assertEqual(report["borrower_type"], "Business")
        self.assertEqual(report["debt_rows"][0]["Monthly payment"], 600)
        self.assertIn(("Cash flow available for debt service (CFADS)", 23000), report["sections"][3]["rows"])
        self.assertEqual(report["currency_confirmed"], True)
        self.assertFalse(any("Personal" in item for item in report["missing"]))

    def test_report_handles_missing_data_and_produces_pdf_and_csv(self):
        report = build_financial_report_data({"borrower_type": "Personal", "applicant_name": "Missing Data"}, "APP-MISSING")
        self.assertTrue(report["missing"])
        self.assertIn("Not available", _financial_report_csv(report, {"analyst_comments": "Internal note"}).decode("utf-8-sig"))
        pdf = _financial_report_pdf(_financial_report_lines(report, {}))
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertTrue(pdf.endswith(b"%%EOF"))

    def test_income_inputs_are_normalized_only_when_complete(self):
        personal = {"financial_analysis": {"income_cash_flow": {"income_sources": [
            {"gross_amount": 5000, "net_amount": 4000, "frequency": "Monthly"},
        ]}}}
        self.assertEqual(personal_monthly_income(personal), (5000, 4000))
        business = {"financial_analysis": {"income_cash_flow": {
            "income_sources": [{"type": "Business revenue", "gross_amount": 20000, "frequency": "Monthly"}],
            "other_operating_income_reviewed": True,
        }}}
        self.assertEqual(business_monthly_operating_income(business), (20000, 0, True))

    def test_business_loan_purpose_does_not_infer_business_borrower_type(self):
        jordan = create_loan_application_demo_data()[1]
        self.assertEqual(jordan["loan_purpose"], "Business")
        self.assertEqual(_borrower_type(jordan), "Not specified")

    def test_explicit_business_type_and_fields_are_recognized(self):
        business = {
            "borrower_type": "Business",
            "business_name": "Example Trading Ltd.",
            "monthly_business_revenue": 25000,
        }
        self.assertEqual(_borrower_type(business), "Business")
        state = _information_state(business)
        self.assertIn(("Business revenue", "monthly_business_revenue"), state["available"])
        self.assertIn("Business type", state["missing"])

    def test_applicant_values_are_unverified_without_explicit_verification(self):
        record = create_loan_application_demo_data()[2]
        state = _information_state(record)
        self.assertIn(("Monthly income", "monthly_income"), state["available"])
        self.assertIn("Monthly income", state["unverified"])
        self.assertIn("Borrower type", state["missing"])


class DebtAnalysisPageTests(unittest.TestCase):
    def test_financial_report_renders_preview_findings_and_export_controls(self):
        record = create_loan_application_demo_data()[2]
        record["borrower_type"] = "Personal"
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [record]
        app.run()
        app.button(key="navigation-Debt & Affordability").click().run()
        rendered = "\n".join(item.value for item in app.markdown)
        self.assertFalse(app.exception)
        self.assertIn("Internal Financial Analysis", rendered)
        self.assertIn("For Review Purposes Only", rendered)
        self.assertIn("Positive financial findings", "\n".join(item.label for item in app.text_area))
        self.assertEqual({button.label for button in app.get("download_button")}, {"Download PDF", "Download CSV"})

    def test_financial_report_switches_with_selected_application(self):
        first = create_loan_application_demo_data()[2]
        first.update(borrower_type="Personal", applicant_name="First Report Applicant", submitted_for_assessment=True)
        second = create_loan_application_demo_data()[0]
        second.update(application_id="APP-SECOND-REPORT", borrower_type="Business", business_name="Second Report Business", submitted_for_assessment=True)
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [first, second]
        app.run()
        app.button(key="navigation-Debt & Affordability").click().run()
        app.selectbox(key="debt-analysis-application-selector").select("APP-SECOND-REPORT").run()
        report_markup = "\n".join(item.value for item in app.markdown)
        self.assertFalse(app.exception)
        self.assertIn("Second Report Business", report_markup)
        self.assertIn("APP-SECOND-REPORT", report_markup)

    def test_scenario_analysis_saves_a_separate_per_application_snapshot(self):
        record = create_loan_application_demo_data()[2]
        record.update(borrower_type="Personal", loan_amount=12000, loan_term_months=12)
        record["financial_analysis"] = {
            "income_cash_flow": {
                "borrower_type": "Personal", "currency": "USD", "currency_confirmed": True,
                "income_sources": [{"name": "Salary", "type": "Employment", "gross_amount": 5000,
                                    "net_amount": 4000, "frequency": "Monthly"}],
                "business_expenses": [],
            },
            "obligations": {
                "personal_living_expenses": [
                    {"category": category, "amount": 100, "frequency": "Monthly", "entry_source": "Applicant-declared"}
                    for category in PERSONAL_EXPENSE_CATEGORIES
                ],
                "personal_debts": [], "personal_no_debts_reported": True,
            },
        }
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [record]
        app.run()
        app.button(key="navigation-Debt & Affordability").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Scenario Analysis & Stress Testing" in item.value for item in app.markdown))
        app.text_input(key="scenario-name-APP-DEMO-0003").set_value("Zero rate review").run()
        app.button(key="scenario-save-APP-DEMO-0003").click().run()
        self.assertFalse(app.exception)
        stored = app.session_state["loan_application_records"][0]
        snapshots = stored["financial_analysis"]["scenario_analysis"]["APP-DEMO-0003"]
        self.assertEqual(snapshots[0]["name"], "Zero rate review")
        self.assertEqual(stored["loan_amount"], 12000)
        self.assertEqual(stored["loan_term_months"], 12)

    def test_part_one_page_selects_only_assessment_eligible_records(self):
        app = AppTest.from_file(str(APP_PATH)).run()
        app.button(key="navigation-Debt & Affordability").click().run()

        self.assertFalse(app.exception)
        self.assertEqual(
            [tab.label for tab in app.get("tab")],
            [
                "Financial Overview",
                "Income & Cash Flow",
                "Expenses & Debts",
                "Repayment Capacity",
                "Scenario Analysis",
                "Financial Report",
            ],
        )
        self.assertEqual(app.selectbox(key="debt-analysis-application-selector").value, "APP-DEMO-0003")
        self.assertIn("Financial Analysis", "\n".join(item.value for item in app.markdown))
        self.assertIn("Not specified", "\n".join(item.value for item in app.markdown))
        self.assertIn("No repayment calculations are performed in Part 1", "\n".join(item.value for item in app.markdown))

    def test_application_search_and_type_filter(self):
        app = AppTest.from_file(str(APP_PATH)).run()
        app.button(key="navigation-Debt & Affordability").click().run()
        app.text_input(key="debt-analysis-search").set_value("Casey").run()
        self.assertEqual(app.selectbox(key="debt-analysis-application-selector").value, "APP-DEMO-0003")

        app.selectbox(key="debt-analysis-borrower-filter").select("Personal").run()
        self.assertTrue(any("No eligible applications match" in item.value for item in app.info))
        self.assertFalse(app.exception)

    def test_no_assessment_eligible_applications_are_explained(self):
        records = create_loan_application_demo_data()
        for record in records:
            record["status"] = "Pending"
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = records
        app.run()
        app.button(key="navigation-Debt & Affordability").click().run()

        self.assertTrue(any("No applications are currently eligible" in item.value for item in app.info))
        self.assertFalse(any(selectbox.key == "debt-analysis-application-selector" for selectbox in app.selectbox))
        self.assertFalse(app.exception)

    def test_explicit_business_record_uses_business_overview(self):
        record = create_loan_application_demo_data()[2]
        record.update(
            borrower_type="Business",
            business_name="Demo Business Ltd.",
            monthly_business_revenue=25000,
            monthly_operating_expenses=18000,
        )
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [record]
        app.run()
        app.button(key="navigation-Debt & Affordability").click().run()

        rendered = "\n".join(item.value for item in app.markdown)
        self.assertIn("Business financial overview", rendered)
        self.assertIn("Demo Business Ltd.", rendered)
        self.assertFalse(app.exception)

    def test_personal_income_analysis_renders_normalized_source_breakdown(self):
        record = create_loan_application_demo_data()[2]
        record["financial_analysis"] = {"income_cash_flow": {
            "borrower_type": "Personal", "currency": "USD", "currency_confirmed": True,
            "income_sources": [{"name": "Primary job", "type": "Employment", "gross_amount": 1200,
                                "net_amount": 1000, "frequency": "Weekly", "verification_status": "Unverified"}],
            "business_expenses": [],
        }}
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [record]
        app.run()
        app.button(key="navigation-Debt & Affordability").click().run()
        rendered = "\n".join(item.value for item in app.markdown)
        self.assertFalse(app.exception)
        self.assertIn("Personal income sources", rendered)
        self.assertIn("5,200.00", rendered)
        self.assertIn("4,333.33", rendered)

    def test_business_cash_flow_requires_all_expense_categories(self):
        record = create_loan_application_demo_data()[2]
        record["borrower_type"] = "Business"
        record["financial_analysis"] = {"income_cash_flow": {
            "currency": "USD", "currency_confirmed": True, "other_operating_income_reviewed": True,
            "income_sources": [{"name": "Sales", "type": "Business revenue", "gross_amount": 20000,
                                "frequency": "Monthly", "verification_status": "Unverified"}],
            "business_expenses": [{"category": category, "amount": 1000, "frequency": "Monthly",
                                   "verification_status": "Unverified"} for category in BUSINESS_EXPENSE_CATEGORIES],
        }}
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [record]
        app.run()
        app.button(key="navigation-Debt & Affordability").click().run()
        rendered = "\n".join(item.value for item in app.markdown)
        self.assertFalse(app.exception)
        self.assertIn("Monthly CFADS", rendered)
        self.assertIn("12,000.00", rendered)

    def test_unclassified_application_requires_explicit_analysis_view(self):
        app = AppTest.from_file(str(APP_PATH)).run()
        app.button(key="navigation-Debt & Affordability").click().run()
        self.assertTrue(any("Choose a working analysis view" in item.value for item in app.info))
        self.assertFalse(app.exception)

    def test_personal_income_form_saves_source_and_verification_state_to_shared_record(self):
        record = create_loan_application_demo_data()[2]
        record["financial_analysis"] = {"income_cash_flow": {
            "borrower_type": "Personal", "currency": "USD", "currency_confirmed": True,
            "income_sources": [], "business_expenses": [],
        }}
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [record]
        app.run()
        app.button(key="navigation-Debt & Affordability").click().run()
        next(item for item in app.text_input if item.label == "Source name").set_value("Payroll")
        next(item for item in app.number_input if item.label == "Gross amount").set_value(3000)
        next(item for item in app.number_input if item.label == "Net amount (optional)").set_value(2400)
        app.button(key="FormSubmitter:personal-income-form-APP-DEMO-0003-Add income source").click().run()
        saved = app.session_state["loan_application_records"][0]
        sources = saved["financial_analysis"]["income_cash_flow"]["income_sources"]
        self.assertEqual(sources[0]["name"], "Payroll")
        self.assertEqual(sources[0]["gross_amount"], 3000)
        self.assertEqual(sources[0]["net_amount"], 2400)
        self.assertEqual(sources[0]["verification_status"], "Unverified")
        self.assertEqual(saved["monthly_income"], 3600)
        self.assertFalse(app.exception)

    def test_personal_expense_and_debt_forms_save_separate_values(self):
        record = create_loan_application_demo_data()[2]
        record["borrower_type"] = "Personal"
        record["financial_analysis"] = {"income_cash_flow": {"currency": "USD", "currency_confirmed": True, "income_sources": [], "business_expenses": []}}
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [record]
        app.run()
        app.button(key="navigation-Debt & Affordability").click().run()
        next(item for item in app.number_input if item.label == "Amount (blank if unknown; use zero if confirmed none)").set_value(400)
        next(item for item in app.button if item.key == "FormSubmitter:expense-entry-form-APP-DEMO-0003-personal-Save expense").click().run()
        next(item for item in app.number_input if item.label == "Outstanding balance (blank if unknown)").set_value(5000)
        next(item for item in app.number_input if item.label == "Monthly repayment / service (blank if unknown)").set_value(250)
        app.button(key="FormSubmitter:debt-entry-form-APP-DEMO-0003-personal-Save debt").click().run()
        obligations = app.session_state["loan_application_records"][0]["financial_analysis"]["obligations"]
        self.assertEqual(obligations["personal_living_expenses"][0]["category"], PERSONAL_EXPENSE_CATEGORIES[0])
        self.assertEqual(obligations["personal_living_expenses"][0]["amount"], 400)
        self.assertEqual(obligations["personal_debts"][0]["outstanding_balance"], 5000)
        self.assertEqual(obligations["personal_debts"][0]["monthly_payment"], 250)
        self.assertEqual(app.session_state["loan_application_records"][0]["existing_debt"], 2100)
        self.assertFalse(app.exception)

    def test_business_expenses_view_reuses_part_two_rows(self):
        record = create_loan_application_demo_data()[2]
        record["borrower_type"] = "Business"
        record["financial_analysis"] = {"income_cash_flow": {
            "currency": "USD", "currency_confirmed": True, "income_sources": [],
            "business_expenses": [{"category": category, "amount": 100, "frequency": "Monthly", "verification_status": "Unverified"} for category in BUSINESS_EXPENSE_CATEGORIES],
        }}
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [record]
        app.run()
        app.button(key="navigation-Debt & Affordability").click().run()
        rendered = "\n".join(item.value for item in app.markdown)
        self.assertIn("Business Operating Expenses", rendered)
        self.assertIn("Part 2 entry (source not specified)", rendered)
        self.assertIn("Total operating expenses", rendered)
        self.assertFalse(app.exception)

    def test_business_operating_expense_form_saves_with_source_and_verification(self):
        record = create_loan_application_demo_data()[2]
        record["borrower_type"] = "Business"
        record["financial_analysis"] = {"income_cash_flow": {"currency": "USD", "currency_confirmed": True, "income_sources": [], "business_expenses": []}}
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [record]
        app.run()
        app.button(key="navigation-Debt & Affordability").click().run()
        next(item for item in reversed(app.selectbox) if item.label == "Expense category").select("Rent")
        next(item for item in app.number_input if item.label == "Amount (blank if unknown; use zero if confirmed none)").set_value(1250)
        app.button(key="FormSubmitter:expense-entry-form-APP-DEMO-0003-business-Save expense").click().run()
        saved = app.session_state["loan_application_records"][0]
        expense = saved["financial_analysis"]["obligations"]["business_operating_expenses"][0]
        self.assertEqual(expense["category"], "Rent")
        self.assertEqual(expense["amount"], 1250)
        self.assertEqual(expense["entry_source"], "Applicant-declared")
        self.assertEqual(expense["verification_status"], "Unverified")
        self.assertFalse(app.exception)

    def test_switching_application_uses_each_records_own_obligations(self):
        records = create_loan_application_demo_data()
        records[0]["status"] = "Under Assessment"
        records[0]["borrower_type"] = "Business"
        records[0]["financial_analysis"] = {"income_cash_flow": {"borrower_type": "Business", "currency": "USD", "currency_confirmed": True, "income_sources": [], "business_expenses": []}, "obligations": {"business_operating_expenses": [{"category": "Rent", "amount": 123, "frequency": "Monthly", "entry_source": "Applicant-declared"}]}}
        records[2]["borrower_type"] = "Personal"
        records[2]["financial_analysis"] = {"income_cash_flow": {"currency": "USD", "currency_confirmed": True, "income_sources": [], "business_expenses": []}, "obligations": {"personal_living_expenses": [{"category": "Housing / Rent", "amount": 456, "frequency": "Monthly", "entry_source": "Applicant-declared"}]}}
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = records
        app.run()
        app.button(key="navigation-Debt & Affordability").click().run()
        selector = app.selectbox(key="debt-analysis-application-selector")
        selector.select("APP-DEMO-0001").run()
        self.assertIn("Business Operating Expenses", "\n".join(item.value for item in app.markdown))
        selector.select("APP-DEMO-0003").run()
        rendered = "\n".join(item.value for item in app.markdown)
        self.assertIn("Living Expenses", rendered)
        self.assertIn("456.00", rendered)
        self.assertFalse(app.exception)

    def test_personal_repayment_capacity_renders_and_saves_calculations(self):
        record = create_loan_application_demo_data()[2]
        record.update(borrower_type="Personal", repayment_frequency="Monthly")
        record["financial_analysis"] = {
            "income_cash_flow": {"currency": "USD", "currency_confirmed": True, "borrower_type": "Personal", "income_sources": [
                {"name": "Salary", "type": "Employment", "gross_amount": 5000, "net_amount": 4000, "frequency": "Monthly"},
            ], "business_expenses": []},
            "obligations": {
                "personal_living_expenses": [{"category": category, "amount": 100, "frequency": "Monthly", "entry_source": "Applicant-declared"} for category in PERSONAL_EXPENSE_CATEGORIES],
                "personal_debts": [{"debt_identity": "loan-1", "debt_type": PERSONAL_DEBT_TYPES[0], "outstanding_balance": 5000, "monthly_payment": 500, "payment_frequency": "Monthly", "entry_source": "Applicant-declared"}],
            },
        }
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [record]
        app.run()
        app.button(key="navigation-Debt & Affordability").click().run(timeout=10)
        app.number_input(key="capacity-loan-amount-APP-DEMO-0003").set_value(12000)
        app.number_input(key="capacity-annual-rate-APP-DEMO-0003").set_value(0)
        app.number_input(key="capacity-term-APP-DEMO-0003").set_value(12)
        app.run(timeout=10)
        rendered = "\n".join(item.value for item in app.markdown)
        self.assertIn("Debt-to-Income Ratio (DTI)", rendered)
        self.assertIn("10.00%", rendered)
        self.assertIn("30.00%", rendered)
        self.assertIn("1,800.00", rendered)
        saved = app.session_state["loan_application_records"][0]["financial_analysis"]["repayment_capacity"]
        self.assertEqual(saved["calculator"]["total_interest"], 0)
        self.assertEqual(saved["personal"]["remaining_income"], 1800)
        self.assertEqual(app.session_state["loan_application_records"][0]["loan_amount"], 8500)
        self.assertEqual(app.session_state["loan_application_records"][0]["loan_term_months"], 24)
        self.assertFalse(app.exception)

    def test_business_repayment_capacity_uses_cfads_and_separate_business_debt(self):
        record = create_loan_application_demo_data()[2]
        record.update(borrower_type="Business", repayment_frequency="Monthly")
        record["financial_analysis"] = {
            "income_cash_flow": {
                "currency": "USD", "currency_confirmed": True, "other_operating_income_reviewed": True,
                "income_sources": [
                    {"type": "Business revenue", "gross_amount": 20000, "frequency": "Monthly"},
                    {"type": "Other operating income", "gross_amount": 1000, "frequency": "Monthly"},
                ],
                "business_expenses": [{"category": category, "amount": 1000, "frequency": "Monthly", "verification_status": "Unverified"} for category in BUSINESS_EXPENSE_CATEGORIES],
            },
            "obligations": {"business_debts": [{"debt_identity": "business-loan", "debt_type": "Existing Business Loans", "outstanding_balance": 12000, "monthly_payment": 1500, "payment_frequency": "Monthly", "entry_source": "Applicant-declared"}]},
        }
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = [record]
        app.run()
        app.button(key="navigation-Debt & Affordability").click().run(timeout=10)
        app.number_input(key="capacity-loan-amount-APP-DEMO-0003").set_value(12000)
        app.number_input(key="capacity-annual-rate-APP-DEMO-0003").set_value(0)
        app.number_input(key="capacity-term-APP-DEMO-0003").set_value(12)
        app.run(timeout=10)
        rendered = "\n".join(item.value for item in app.markdown)
        self.assertIn("Cash flow available for debt service", rendered)
        self.assertIn("13,000.00", rendered)
        self.assertIn("5.20", rendered)
        self.assertIn("10,500.00", rendered)
        saved = app.session_state["loan_application_records"][0]["financial_analysis"]["repayment_capacity"]["business"]
        self.assertEqual(saved["total_monthly_debt_service"], 2500)
        self.assertFalse(app.exception)

    def test_repayment_capacity_switches_with_selected_application(self):
        records = create_loan_application_demo_data()
        for record, gross, net in ((records[0], 1000, 900), (records[2], 2000, 1500)):
            record["status"] = "Under Assessment"
            record["borrower_type"] = "Personal"
            record["annual_interest_rate"] = 0
            record["financial_analysis"] = {
                "income_cash_flow": {"currency": "USD", "currency_confirmed": True, "income_sources": [
                    {"gross_amount": gross, "net_amount": net, "frequency": "Monthly"},
                ], "business_expenses": []},
                "obligations": {
                    "personal_living_expenses": [{"category": category, "amount": 0, "frequency": "Monthly", "entry_source": "Applicant-declared"} for category in PERSONAL_EXPENSE_CATEGORIES],
                    "personal_no_debts_reported": True,
                },
            }
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["loan_application_records"] = records
        app.run()
        app.button(key="navigation-Debt & Affordability").click().run()
        app.selectbox(key="debt-analysis-application-selector").select("APP-DEMO-0001").run()
        self.assertIn("1,000.00", "\n".join(item.value for item in app.markdown))
        app.selectbox(key="debt-analysis-application-selector").select("APP-DEMO-0003").run()
        rendered = "\n".join(item.value for item in app.markdown)
        self.assertIn("2,000.00", rendered)
        self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
