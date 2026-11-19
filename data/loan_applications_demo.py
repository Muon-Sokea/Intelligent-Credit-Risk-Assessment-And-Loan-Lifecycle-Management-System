"""Clearly illustrative Loan Applications records for the prototype."""

from datetime import date, datetime, time, timedelta, timezone


_RECORDS = (
    {
        "applicant_name": "Taylor Reed",
        "days_ago": 2,
        "loan_amount": 12500,
        "loan_purpose": "Personal",
        "risk_level": "Medium",
        "status": "Pending",
        "date_of_birth": date(1991, 4, 12),
        "gender": "Prefer not to say",
        "phone": "+1 202-555-0101",
        "email": "taylor.reed@example.invalid",
        "address": "Sample District, Demo City",
        "employment_status": "Full-time",
        "occupation": "Project coordinator",
        "employer_name": "Sample Works Ltd.",
        "work_experience_years": 5,
        "monthly_income": 5200,
        "monthly_expenses": 2450,
        "existing_debt": 6800,
        "other_obligations": 350,
        "loan_term_months": 36,
        "repayment_frequency": "Monthly",
    },
    {
        "applicant_name": "Jordan Ellis",
        "days_ago": 6,
        "loan_amount": 32000,
        "loan_purpose": "Business",
        "risk_level": "High",
        "status": "Under Review",
        "date_of_birth": date(1987, 9, 3),
        "gender": "Male",
        "phone": "+1 202-555-0102",
        "email": "jordan.ellis@example.invalid",
        "address": "Sample Quarter, Demo City",
        "employment_status": "Self-employed",
        "occupation": "Retail owner",
        "employer_name": "Ellis Demo Trading",
        "work_experience_years": 8,
        "monthly_income": 7800,
        "monthly_expenses": 3900,
        "existing_debt": 14200,
        "other_obligations": 520,
        "loan_term_months": 48,
        "repayment_frequency": "Monthly",
    },
    {
        "applicant_name": "Casey Park",
        "days_ago": 12,
        "loan_amount": 8500,
        "loan_purpose": "Education",
        "risk_level": "Low",
        "status": "Under Assessment",
        "date_of_birth": date(1995, 1, 28),
        "gender": "Female",
        "phone": "+1 202-555-0103",
        "email": "casey.park@example.invalid",
        "address": "Example Ward, Demo City",
        "employment_status": "Part-time",
        "occupation": "Library assistant",
        "employer_name": "Demo Learning Center",
        "work_experience_years": 3,
        "monthly_income": 3600,
        "monthly_expenses": 1750,
        "existing_debt": 2100,
        "other_obligations": 180,
        "loan_term_months": 24,
        "repayment_frequency": "Monthly",
    },
    {
        "applicant_name": "Morgan Blake",
        "days_ago": 20,
        "loan_amount": 85000,
        "loan_purpose": "Home",
        "risk_level": "Medium",
        "status": "Approved",
        "date_of_birth": date(1984, 6, 9),
        "gender": "Female",
        "phone": "+1 202-555-0104",
        "email": "morgan.blake@example.invalid",
        "address": "Sample Heights, Demo City",
        "employment_status": "Full-time",
        "occupation": "Operations manager",
        "employer_name": "Example Services Group",
        "work_experience_years": 12,
        "monthly_income": 9600,
        "monthly_expenses": 4100,
        "existing_debt": 22500,
        "other_obligations": 640,
        "loan_term_months": 180,
        "repayment_frequency": "Monthly",
    },
    {
        "applicant_name": "Avery Quinn",
        "days_ago": 35,
        "loan_amount": 6000,
        "loan_purpose": "Other",
        "risk_level": "Not Assessed",
        "status": "Rejected",
        "date_of_birth": date(1992, 11, 17),
        "gender": "Non-binary",
        "phone": "+1 202-555-0105",
        "email": "avery.quinn@example.invalid",
        "address": "Example Park, Demo City",
        "employment_status": "Contract",
        "occupation": "Design assistant",
        "employer_name": "Sample Creative Co.",
        "work_experience_years": 4,
        "monthly_income": 4400,
        "monthly_expenses": 2350,
        "existing_debt": 5100,
        "other_obligations": 260,
        "loan_term_months": 24,
        "repayment_frequency": "Monthly",
    },
    {
        "applicant_name": "Riley Chen",
        "days_ago": 52,
        "loan_amount": 18500,
        "loan_purpose": "Personal",
        "risk_level": "High",
        "status": "Under Review",
        "date_of_birth": date(1989, 2, 21),
        "gender": "Male",
        "phone": "+1 202-555-0106",
        "email": "riley.chen@example.invalid",
        "address": "Demo Garden District, Demo City",
        "employment_status": "Full-time",
        "occupation": "Systems technician",
        "employer_name": "Sample Network Labs",
        "work_experience_years": 7,
        "monthly_income": 6900,
        "monthly_expenses": 3100,
        "existing_debt": 17600,
        "other_obligations": 470,
        "loan_term_months": 48,
        "repayment_frequency": "Bi-weekly",
    },
)


def create_loan_application_demo_data(reference_date: date | None = None) -> list[dict]:
    """Return fresh sample records with dates relative to a reference day."""
    today = reference_date or date.today()
    records = []

    for index, template in enumerate(_RECORDS, start=1):
        days_ago = template["days_ago"]
        application_date = today - timedelta(days=days_ago)
        history = [
            {
                "event": "Application submitted",
                "timestamp": datetime.combine(
                    application_date,
                    time(hour=9 + index % 6, minute=15),
                    tzinfo=timezone.utc,
                ),
            }
        ]

        if template["status"] in {
            "Under Review",
            "Under Assessment",
            "Approved",
            "Rejected",
        }:
            history.append(
                {
                    "event": "Initial review",
                    "timestamp": datetime.combine(
                        application_date + timedelta(days=1),
                        time(hour=10, minute=30),
                        tzinfo=timezone.utc,
                    ),
                }
            )

        if template["status"] in {"Under Assessment", "Approved", "Rejected"}:
            history.append(
                {
                    "event": "Assessment step recorded in demo data",
                    "timestamp": datetime.combine(
                        application_date + timedelta(days=2),
                        time(hour=14, minute=0),
                        tzinfo=timezone.utc,
                    ),
                }
            )

        if template["status"] in {"Approved", "Rejected"}:
            history.append(
                {
                    "event": "Decision status shown in demo data",
                    "timestamp": datetime.combine(
                        application_date + timedelta(days=3),
                        time(hour=11, minute=45),
                        tzinfo=timezone.utc,
                    ),
                }
            )

        record = {
            key: value
            for key, value in template.items()
            if key != "days_ago"
        }
        record.update(
            {
                "application_id": f"APP-DEMO-{index:04d}",
                "application_date": application_date,
                "available_monthly_income": (
                    template["monthly_income"]
                    - template["monthly_expenses"]
                    - template["other_obligations"]
                ),
                "history": history,
            }
        )
        records.append(record)

    return records
