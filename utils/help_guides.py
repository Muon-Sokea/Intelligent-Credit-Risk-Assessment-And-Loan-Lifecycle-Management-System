"""User guide content for each FinGuard AI module."""

GUIDES = {}


def _guide(guide_id, title, category, read_time, summary, intro, sections, related):
    GUIDES[guide_id] = {
        "id": guide_id,
        "title": title,
        "category": category,
        "read_time": read_time,
        "summary": summary,
        "intro": intro,
        "sections": sections,
        "related": related,
    }


_guide(
    "guide-dashboard",
    "Dashboard Guide",
    "Dashboard",
    6,
    "Read the portfolio snapshot, KPI cards, charts, alerts, and date filters.",
    "The Dashboard is the first screen after launch. It summarises the demonstration portfolio for a chosen reporting period. Every figure on this page is illustrative sample data and is not connected to a live banking system.",
    (
        {
            "heading": "1. Dashboard introduction",
            "body": (
                "The page is organised into four areas: the reporting period selector, four KPI cards, a portfolio overview row with trends and risk distribution, and a repayment and recent-applications section.",
                "Changing the reporting period refilters every panel on the page. The default is the last 90 days.",
            ),
            "steps": (
                "Open Dashboard from the Workspace group in the sidebar.",
                "Confirm the reporting period shown under the Portfolio Snapshot heading.",
                "Read each KPI with its support caption to see what it counts.",
                "Scroll to the charts, alerts, and recent application table.",
            ),
        },
        {
            "heading": "2. Understanding the KPI cards",
            "body": (
                "Total Applications counts sample applications dated inside the reporting period.",
                "Active Loans counts approved sample accounts with an active status whose origination date is in the period. It does not read Loan Monitoring records.",
                "High-Risk Applicants counts applications whose stored risk label is High Risk.",
                "Overdue Loans counts sample loans whose due date has passed with an Overdue payment status.",
            ),
            "steps": (
                "Hover a KPI card title beside the small help icon for a definition.",
                "Compare the KPI support caption with the selected date range before drawing conclusions.",
            ),
            "note": "KPI values are demonstration figures, not a production portfolio snapshot.",
        },
        {
            "heading": "3. Understanding application trends",
            "body": (
                "The Loan portfolio trends panel plots monthly sample loan amounts as a line and monthly application counts as bars. The panel caption marks the data as demo data.",
            ),
            "steps": (
                "Hover the line or bars to see exact values in the tooltip.",
                "Use the period selector to compare shorter and longer windows.",
            ),
        },
        {
            "heading": "4. Actual disbursement trends",
            "body": (
                "The Dashboard does not display actual disbursement amounts. Actual disbursements are recorded in Loan Monitoring and analysed in Banking Analytics, using real recorded disbursement dates, amounts, and currency.",
            ),
            "note": "Do not read the Dashboard portfolio trend as an actual disbursement figure.",
        },
        {
            "heading": "5. Understanding credit risk distribution",
            "body": (
                "The doughnut chart groups sample applicants into Low Risk, Medium Risk, and High Risk. Categories are read from the sample records; the chart does not calculate a score.",
            ),
            "steps": (
                "Check the percentages beside each label.",
                "Hover a slice to see the applicant count.",
            ),
        },
        {
            "heading": "6. Understanding repayment performance",
            "body": (
                "The repayment panel compares On-time and Late recorded sample payments as a share of all recorded payments in the selected period. It is a payment outcome view, not a full repayment schedule analysis.",
            ),
        },
        {
            "heading": "7. Understanding risk and repayment alerts",
            "body": (
                "Three illustrative alert cards highlight a manual review, an overdue repayment, and an affordability follow-up. They are static sample content and are not generated from live monitoring rules.",
            ),
        },
        {
            "heading": "8. Using date filters",
            "body": (
                "The reporting period selector offers 7, 30, and 90 days, the current year, or a custom range.",
            ),
            "steps": (
                "Choose Custom date range to reveal two date inputs.",
                "Select a start and end date; the KPI and chart panels update on the next rerun.",
                "Confirm the caption under the snapshot heading shows the dates actually applied.",
            ),
            "note": "If the period excludes the sample records, panels show a clear empty state rather than zero-filled charts.",
        },
        {
            "heading": "9. Understanding recent applications",
            "body": (
                "The recent applications table lists the newest sample applications in the selected period, with application ID, applicant, date, amount, risk level, and status.",
            ),
            "steps": (
                "Scroll the table horizontally if your screen is narrow.",
                "Use Loan Applications for the full searchable application workspace.",
            ),
        },
    ),
    (
        "guide-dashboard",
        "guide-loan-applications",
        "guide-credit-assessment",
        "guide-banking-analytics",
    ),
)


_guide(
    "guide-loan-applications",
    "Loan Applications Guide",
    "Loan Applications",
    10,
    "Create, search, filter, save, submit, and review application records.",
    "Application Management is the shared record workspace. Records created here feed Credit Assessment, Debt & Affordability, Loan Monitoring, and Banking Analytics through the application ID.",
    (
        {
            "heading": "1. Understanding the workspace",
            "body": (
                "The list view shows summary counts, filters, and a paginated table of application records. The navbar New Application button and the page action both open the four-step application form.",
                "The workspace uses the shared loan_application_records session data. Help & Support never creates or changes these records.",
            ),
            "steps": (
                "Open Loan Applications from the Workspace group.",
                "Use the summary tiles to see the total and status mix.",
                "Open a row to view full details.",
            ),
        },
        {
            "heading": "2. Viewing application records",
            "body": (
                "Each row shows application ID, applicant, date, amount, purpose, risk label, and status. Opening a record shows the applicant, employment, financial, loan request, and history sections.",
            ),
            "steps": (
                "Select View beside a record in the table.",
                "Read the detail sections top to bottom.",
                "Use the back action to return to the list without losing filters.",
            ),
        },
        {
            "heading": "3. Searching for applicants",
            "body": (
                "Search matches application ID and applicant name using a case-insensitive partial match.",
            ),
            "steps": (
                "Type part of an applicant name or application ID in the search field.",
                "Confirm the result count shown above the table.",
                "Clear the search to restore all records.",
            ),
        },
        {
            "heading": "4. Using application filters",
            "body": (
                "Status, purpose, and date filters combine with search. Pagination resets when filters change.",
            ),
            "steps": (
                "Choose a status and loan purpose.",
                "Set the application date range.",
                "Review the filtered count before exporting.",
            ),
            "note": "If no records match, widen the date range or clear a filter rather than assuming records were lost.",
        },
        {
            "heading": "5. Creating new applications",
            "body": (
                "The form has four steps: applicant details, employment and income, expenses and obligations, and loan request. Required fields are marked and validated before moving forward.",
            ),
            "steps": (
                "Select New Application.",
                "Complete the applicant step, then continue.",
                "Review each step before advancing.",
                "Use Previous to correct an earlier step.",
            ),
        },
        {
            "heading": "6. Entering applicant information",
            "body": (
                "Includes full name, date of birth, gender, phone, email, and residential address. Date of birth cannot be in the future.",
            ),
            "note": "Enter only the information needed for the prototype; do not paste real sensitive customer data into a demo environment.",
        },
        {
            "heading": "7. Entering employment or business information",
            "body": (
                "Record employment status, occupation, employer, work experience, and monthly income. Self-employed applicants can record their business name as the employer.",
            ),
        },
        {
            "heading": "8. Entering the loan request",
            "body": (
                "Record monthly expenses, existing debt, other obligations, requested amount, purpose, term, and repayment frequency. These values feed affordability analysis once the application is in the assessment workflow.",
            ),
            "steps": (
                "Enter expenses and obligations accurately; they are not the same as the requested loan.",
                "Choose the term in months and the repayment frequency.",
                "Check the requested amount against the purpose before saving.",
            ),
        },
        {
            "heading": "9. Supporting documents",
            "body": (
                "Loan Applications does not implement document upload. Document verification is a status recorded during Credit Assessment; no files are stored or inspected by the prototype.",
            ),
            "note": "Do not expect an attachment field on the application form.",
        },
        {
            "heading": "10. Saving applications",
            "body": (
                "Saving stores the record in the shared session state. A saved record can be reopened and edited while the session remains active.",
            ),
            "steps": (
                "Use Save on the final step to keep the record without advancing its workflow stage.",
                "Confirm the success notice and return to the list.",
            ),
        },
        {
            "heading": "11. Submitting applications",
            "body": (
                "Submitting validates and saves the record and records a submission event in its history. It does not approve the loan and does not create a disbursement.",
            ),
            "note": "Submission is an application workflow action only. Approval requires a separate final lending decision, and monitoring requires an explicit disbursement.",
        },
        {
            "heading": "12. Understanding application statuses",
            "body": (
                "Pending means the application has been recorded but review has not started. Under Review means initial review is in progress. Under Assessment means it has entered the credit workflow. Approved means the record carries an approved status in this prototype. Rejected means the application was declined.",
                "A status is a workflow label. It is not the same as an analyst recommendation, a final lending decision, or a disbursed loan.",
            ),
        },
        {
            "heading": "13. Viewing application details",
            "body": (
                "The detail view presents applicant, employment, financial, and loan request information together with the application history and stored risk summary.",
            ),
        },
        {
            "heading": "14. Eligibility for Credit Assessment",
            "body": (
                "Only applications whose status is Under Assessment, Assessment Completed, or Pending Decision appear in Credit Assessment. Pending and Under Review records are excluded until they reach the assessment stage.",
            ),
            "steps": (
                "Open the application and check its status.",
                "If it is Pending or Under Review, move it to the assessment stage in the application workspace first.",
                "Return to Credit Assessment and reselect the application.",
            ),
        },
        {
            "heading": "15. Exporting application information",
            "body": (
                "The table view supports CSV and Excel export of the filtered application columns. PDF export is not provided here.",
            ),
            "steps": (
                "Apply search and filters first so the export matches what you see.",
                "Use the CSV or Excel download action.",
                "Open the file and confirm the row count matches the filtered count.",
            ),
            "note": "Exports contain the filtered records only and include personal applicant fields; handle the files appropriately.",
        },
    ),
    (
        "guide-dashboard",
        "guide-credit-assessment",
        "guide-debt-affordability",
        "faq-applications-status",
    ),
)


_guide(
    "guide-credit-assessment",
    "Credit Assessment Guide",
    "Credit Assessment",
    9,
    "Review applications, verify documents, record findings, and submit an analyst recommendation.",
    "Credit Assessment is a human-led review workspace over the shared application records. It does not run a machine-learning model and does not make the final lending decision.",
    (
        {
            "heading": "1. Understanding the assessment workspace",
            "body": (
                "The workspace opens with application search and status filters, then an application selector. The selected record is shown through six tabs: Assessment Overview, Applicant & Documents, Financial & Credit Analysis, Credit Risk Assessment, Findings & Recommendation, and Assessment History.",
                "Assessment status values are Not Started, In Progress, Awaiting Information, and Completed.",
            ),
        },
        {
            "heading": "2. Selecting eligible applications",
            "body": (
                "Only applications whose application status is Under Assessment, Assessment Completed, or Pending Decision appear in the selector. Pending and Under Review applications are intentionally excluded.",
            ),
            "steps": (
                "Use the search field for an application ID or applicant name.",
                "Narrow by assessment status or loan purpose.",
                "Choose a record from the application selector.",
            ),
            "note": "If the selector is empty, move the application into the assessment workflow from Loan Applications first.",
        },
        {
            "heading": "3. Reviewing applicant information",
            "body": (
                "The Applicant & Documents tab shows identity, contact, employment, and address information from the application record. Treat it as the source of truth for this review.",
            ),
        },
        {
            "heading": "4. Reviewing financial information",
            "body": (
                "The Financial & Credit Analysis tab shows stored income, expenses, obligations, requested loan details, and any calculated DTI, DSTI, or DSCR values. Missing inputs remain blank rather than being filled with estimates.",
                "Debt & Affordability provides the detailed affordability workspace and scenario analysis.",
            ),
        },
        {
            "heading": "5. Reviewing documents",
            "body": (
                "The prototype lists standard document types and lets staff record a status for each. It does not upload, open, or inspect files.",
            ),
            "steps": (
                "Open the Applicant & Documents tab.",
                "For each document type, record the current status.",
                "Add verification notes where useful.",
            ),
        },
        {
            "heading": "6. Understanding document verification statuses",
            "body": (
                "Document statuses are Not Submitted, Pending Review, Verified, and Needs Resubmission. Verification statuses are Verified, Needs Review, Missing, and Needs Resubmission. A Verified status means staff recorded verification, not that an automated check passed.",
            ),
        },
        {
            "heading": "7. Reviewing available financial and credit information",
            "body": (
                "Use the information actually present. A stored risk summary may include a source label; the workspace does not create a credit score or probability of default. If a value is unavailable, record the gap instead of assuming a favourable result.",
            ),
        },
        {
            "heading": "8. Understanding risk indicators",
            "body": (
                "Risk labels such as Low, Medium, High, and Not Assessed are descriptive. They can reflect demo data or a stored human summary. No live ML default model is active in this prototype.",
            ),
        },
        {
            "heading": "9. Recording analyst findings",
            "body": (
                "The Findings & Recommendation tab stores structured findings and comments against the shared application record. Saving findings updates the assessment status and adds an activity entry.",
            ),
            "steps": (
                "Open Findings & Recommendation.",
                "Complete the finding fields relevant to the review.",
                "Select Save findings to keep the work in progress.",
            ),
        },
        {
            "heading": "10. Preparing an analyst recommendation",
            "body": (
                "A recommendation requires a selected recommendation type and a written justification. Without both, submission is blocked.",
            ),
        },
        {
            "heading": "11. Understanding recommendation types",
            "body": (
                "The available recommendations are Recommend Approval, Recommend Rejection, Request Additional Information, and Refer for Further Review. Request Additional Information moves the assessment to Awaiting Information; the others complete the assessment.",
            ),
        },
        {
            "heading": "12. Completing an assessment",
            "body": (
                "Submitting a recommendation records it in the assessment history and marks the assessment Completed or Awaiting Information. It does not change the application to Approved and does not create a loan account.",
            ),
            "steps": (
                "Select a recommendation.",
                "Write a clear justification.",
                "Choose Submit recommendation.",
                "Confirm the success message states that this is not the final lending decision.",
            ),
        },
        {
            "heading": "13. Recommendations versus final lending decisions",
            "body": (
                "An analyst recommendation is advice to the decision maker. A final lending decision is an externally authorized approval or rejection. FinGuard AI treats these as separate fields; only an explicit final decision counts as approved.",
            ),
            "note": "Do not describe an analyst recommendation as an approval in communications or reports.",
        },
        {
            "heading": "14. Assessment history",
            "body": (
                "The history tab combines application history and assessment activity. It is session-based and is not a production audit log; it does not identify individual users.",
            ),
        },
    ),
    (
        "guide-loan-applications",
        "guide-debt-affordability",
        "faq-risk-vs-decision",
        "glossary-credit-risk",
    ),
)


_guide(
    "guide-debt-affordability",
    "Debt & Affordability Guide",
    "Debt & Affordability",
    10,
    "Analyse personal and business affordability, ratios, scenarios, and financial reports.",
    "Financial Analysis evaluates whether an applicant or business can support a proposed loan. Personal and business calculations are kept separate, and no official bank approval threshold is configured.",
    (
        {
            "heading": "1. Understanding Debt & Affordability",
            "body": (
                "Only applications in the assessment workflow appear in this module. Select a record, then work through Financial Overview, Income & Cash Flow, Expenses & Debts, Repayment Capacity, Scenario Analysis, and Financial Report.",
            ),
        },
        {
            "heading": "2. Selecting an application",
            "body": (
                "Use search, borrower type, purpose, application status, and assessment status filters. The selected application drives every tab.",
            ),
            "note": "If no records are available, return to Credit Assessment or move the application into the assessment workflow first.",
        },
        {
            "heading": "3. Understanding personal loan analysis",
            "body": (
                "Personal analysis uses gross monthly income, net monthly income, monthly living expenses, existing monthly debt payments, and the proposed monthly instalment. It calculates DTI, DSTI, disposable income, and remaining income after the new instalment.",
            ),
            "steps": (
                "Confirm the borrower type is Personal.",
                "Enter income in the Income & Cash Flow tab.",
                "Enter living expenses and debt payments in Expenses & Debts.",
                "Review the proposed loan terms before reading the ratios.",
            ),
        },
        {
            "heading": "4. Understanding business loan analysis",
            "body": (
                "Business analysis uses monthly cash flow available for debt service (CFADS), existing monthly debt service, and the proposed instalment. It calculates DSCR and remaining cash flow. Personal DTI and DSTI are not applied to business borrowers.",
            ),
        },
        {
            "heading": "5. Entering income and cash-flow information",
            "body": (
                "Record period-matched figures. For personal borrowers enter both gross and net income. For business borrowers enter CFADS on a monthly basis, matching the debt service period.",
            ),
            "note": "Income fields feed calculations only when the required inputs are complete; missing inputs produce Insufficient Information rather than an estimate.",
        },
        {
            "heading": "6. Entering expenses",
            "body": (
                "Living expenses are separate from debt payments. Do not include existing loan instalments in living expenses, because they are captured separately for DTI and DSTI.",
            ),
        },
        {
            "heading": "7. Recording existing debt",
            "body": (
                "Record monthly debt payments and outstanding balances separately. Monthly payments drive DTI and DSTI. Outstanding balances are informational and are not added to monthly service.",
            ),
        },
        {
            "heading": "8. Understanding DTI",
            "body": (
                "DTI measures the share of gross monthly income already committed to existing monthly debt payments.",
            ),
            "steps": (
                "Formula: DTI = Existing Monthly Debt Payments / Gross Monthly Income x 100.",
                "Example: $500 existing payments and $2,000 gross income give DTI = 25%.",
                "Use the on-screen calculation rather than copying a stale value.",
            ),
        },
        {
            "heading": "9. Understanding DSTI",
            "body": (
                "DSTI adds the proposed monthly instalment to existing debt payments before dividing by gross monthly income. It answers how much of gross income the total debt load would use.",
            ),
            "steps": (
                "Formula: DSTI = (Existing Monthly Debt Payments + Proposed Monthly Instalment) / Gross Monthly Income x 100.",
                "Example: $500 existing plus $300 proposed against $2,000 gross gives DSTI = 40%.",
            ),
        },
        {
            "heading": "10. Understanding DSCR",
            "body": (
                "DSCR applies to business borrowers. It divides monthly CFADS by existing plus proposed monthly debt service.",
            ),
            "steps": (
                "Formula: DSCR = Monthly CFADS / Total Monthly Debt Service.",
                "Example: CFADS $5,000 and debt service $2,500 give DSCR = 2.00x.",
                "A DSCR at or below zero debt service is unavailable, not infinite.",
            ),
        },
        {
            "heading": "11. Reviewing repayment capacity",
            "body": (
                "The Repayment Capacity tab combines the amortising instalment with the ratio calculations. It shows the proposed amount, rate, term, instalment, total repayment, ratios, and remaining income or cash flow.",
                "The interpretation is descriptive. No pass/fail policy is applied in this prototype.",
            ),
        },
        {
            "heading": "12. Using scenario analysis",
            "body": (
                "Scenario Analysis applies hypothetical changes such as an income reduction, expense increase, debt increase, or interest rate rise. It recalculates the view without changing the stored application record.",
            ),
            "steps": (
                "Choose a preset or enter custom changes.",
                "Compare the scenario ratios with the base case.",
                "Label any copied result clearly as hypothetical.",
            ),
        },
        {
            "heading": "13. Understanding affordability results",
            "body": (
                "Insufficient Information means required inputs are missing or invalid, not that the borrower failed. Where ratios exist, read them together with remaining income or cash flow and the assumptions used.",
            ),
        },
        {
            "heading": "14. Generating financial reports",
            "body": (
                "The Financial Report tab presents the analysis in a report layout with export options supported by the module. Review the filters and selected application before exporting.",
            ),
            "note": "Reports are internal working documents and are not audited financial statements.",
        },
    ),
    (
        "guide-credit-assessment",
        "guide-loan-monitoring",
        "faq-dti",
        "glossary-dti",
    ),
)


_guide(
    "guide-loan-monitoring",
    "Loan Monitoring Guide",
    "Loan Monitoring",
    9,
    "Monitor disbursed accounts, repayment schedules, payments, overdue aging, and collection follow-up.",
    "Loan Monitoring covers post-disbursement servicing only. Approved applications are not active loans; an explicit disbursement must be recorded before an account appears here.",
    (
        {
            "heading": "1. Understanding the monitoring workspace",
            "body": (
                "The module has six tabs: Loan Overview, Loan Accounts, Repayment Schedule, Overdue Monitoring, Collection & Follow-up, and Monitoring Reports. The overview shows portfolio totals and empty states when no disbursed accounts exist.",
            ),
        },
        {
            "heading": "2. Approved versus disbursed loans",
            "body": (
                "Eligibility requires a unique loan account ID, an application ID, an explicit disbursement status of Disbursed, a valid disbursement date, a positive amount and currency, and an account status of Active or Fully Repaid. A generic Approved application status does not qualify.",
            ),
            "note": "If a loan is missing here, first check whether the disbursement was actually recorded.",
        },
        {
            "heading": "3. Viewing loan accounts",
            "body": (
                "Loan Accounts lists eligible disbursed accounts with borrower type, loan status, disbursed amount, outstanding balance, overdue amount, and days past due. Use the filters to narrow the list.",
            ),
            "steps": (
                "Open Loan Accounts.",
                "Filter by account status, borrower type, or search text.",
                "Open an account to review its details and transactions.",
            ),
        },
        {
            "heading": "4. Reviewing account details",
            "body": (
                "Account details include the external decision reference, approved terms, disbursement information, schedule, payment transactions, activities, promises, and collection status. Staff-entered decision references are unverified and do not themselves approve a loan.",
            ),
        },
        {
            "heading": "5. Understanding repayment schedules",
            "body": (
                "Schedules use fixed nominal-rate amortisation with monthly or quarterly instalments, cent rounding, and a final principal adjustment. Quarterly terms must divide evenly by three months. A missing schedule on an Active account can be generated after staff confirms the rate, term, frequency, first due date, and currency.",
            ),
            "steps": (
                "Select the account in Repayment Schedule.",
                "Review any existing schedule rows before generating anything.",
                "Enter the authorized terms and confirm generation.",
                "Verify the final instalment adjusts to clear principal exactly.",
            ),
            "note": "Schedules are never reconstructed after payments exist, and cannot be generated for non-Active historical accounts.",
        },
        {
            "heading": "6. Recording full payments",
            "body": (
                "A payment transaction records date, reference, amount received, method, notes, and recorder. Payments allocate to the oldest unpaid instalments, interest first and principal second.",
            ),
        },
        {
            "heading": "7. Recording partial payments",
            "body": (
                "Partial payments are supported. The remainder of the instalment stays scheduled and can become overdue. Overpayments, fees, penalties, reversals, and interest accrual between instalments are not supported.",
            ),
            "steps": (
                "Enter the amount actually received.",
                "Check the allocation preview before saving.",
                "Confirm the affected instalments and remaining scheduled amount.",
            ),
        },
        {
            "heading": "8. Understanding outstanding balances",
            "body": (
                "Outstanding principal equals disbursed principal less actual recorded principal allocations. It is not reduced by scheduled but unpaid amounts and is not the same as the overdue amount.",
            ),
        },
        {
            "heading": "9. Understanding Days Past Due",
            "body": (
                "DPD is the number of calendar days between an unpaid due date and the reference date used by the module. DPD drives overdue aging and analytics bands.",
            ),
        },
        {
            "heading": "10. Understanding overdue aging",
            "body": (
                "Overdue balances are grouped into aging bands such as 1-30, 31-60, 61-90, and more than 90 days. The bands are descriptive and do not automatically apply a default classification.",
            ),
        },
        {
            "heading": "11. Managing collection follow-ups",
            "body": (
                "Collection & Follow-up records contact activity against overdue accounts. Activities are stored separately from payments and do not change balances.",
            ),
        },
        {
            "heading": "12. Recording promises to pay",
            "body": (
                "A promise to pay records a borrower commitment with an amount and date. It is tracked separately and does not create a payment transaction.",
            ),
        },
        {
            "heading": "13. Reviewing monitoring reports",
            "body": (
                "Monitoring Reports provide portfolio, repayment, overdue aging, and collection summaries. Filters apply consistently to the report and its exports. CSV, Excel, and PDF exports are supported.",
            ),
            "note": "Reports are internal and for review purposes only; they are not audited statements.",
        },
    ),
    (
        "guide-banking-analytics",
        "faq-monitoring-eligibility",
        "ts-monitoring-no-eligible",
        "glossary-days-past-due",
    ),
)


_guide(
    "guide-banking-analytics",
    "Banking Analytics Guide",
    "Banking Analytics",
    8,
    "Use portfolio filters and six analytical tabs to interpret applications, risk, and repayment performance.",
    "Banking Analytics is a read-only analytical workspace over the shared application and loan monitoring records. It does not edit accounts or record payments.",
    (
        {
            "heading": "1. Understanding Banking Analytics",
            "body": (
                "The workspace combines application records with eligible disbursed accounts. Application status, explicit final decision status, and loan lifecycle status remain distinct throughout.",
            ),
        },
        {
            "heading": "2. Portfolio Overview",
            "body": (
                "The overview presents application volume and amounts, eligible disbursed accounts, actual disbursements, outstanding principal, and current delinquency indicators, depending on data availability.",
            ),
        },
        {
            "heading": "3. Using global filters",
            "body": (
                "Global filters cover reporting dates, borrower type, loan purpose, application status, decision status, loan status, and stored risk. Date filters use each measure's own event date: application date for application cohorts, disbursement date for disbursement cohorts, due date for scheduled instalments, and payment date for transactions.",
            ),
            "steps": (
                "Set the reporting period first.",
                "Add only the filters needed for the question.",
                "Check the active filter summary before exporting.",
            ),
            "note": "Current outstanding balances and current delinquency use current Loan Monitoring state because historical balance snapshots are not stored.",
        },
        {
            "heading": "4. Loan Portfolio Analysis",
            "body": (
                "This tab analyses requested amounts, approved final decisions, disbursed accounts, and outstanding balances by purpose, borrower type, and status. Actual disbursement figures are shown separately from application amounts.",
            ),
        },
        {
            "heading": "5. Credit Risk Analytics",
            "body": (
                "Risk analytics groups stored risk labels. The module reads summaries and source labels; it never creates a credit score or ML prediction. Missing risk values remain Not Assessed.",
            ),
        },
        {
            "heading": "6. Repayment & Delinquency Analytics",
            "body": (
                "This tab uses repayment schedules, recorded payments, and overdue balances to show repayment rates, aging, delinquency, and PAR indicators. PAR metrics are shown only when complete schedule and balance data support them.",
            ),
        },
        {
            "heading": "7. Customer & Borrower Analytics",
            "body": (
                "Customer analysis summarises borrower types and employment or industry groups without direct names or contact details. Borrower identity is limited in this prototype, so new/returning borrower analysis is not available.",
            ),
        },
        {
            "heading": "8. Financial Performance & Reports",
            "body": (
                "Financial reports present disbursement, payment, and interest allocation summaries where recorded. PDF, Excel, and CSV exports reflect the selected report and filters.",
            ),
        },
        {
            "heading": "9. Understanding charts and indicators",
            "body": (
                "Hover charts for exact values. Not Available or Insufficient Data means the required records or inputs are missing; it does not mean zero. Application and disbursement amounts differ because they measure different events and cohorts.",
            ),
        },
        {
            "heading": "10. Exporting analytical reports",
            "body": (
                "Exports contain only supported fields and current records. Review the report table row count and active filters before downloading.",
            ),
        },
    ),
    (
        "guide-loan-monitoring",
        "faq-par",
        "ts-analytics-no-charts",
        "glossary-portfolio-at-risk",
    ),
)


def get_guide(guide_id):
    """Return a guide by its stable resource id."""
    return GUIDES.get(guide_id)


def guide_order():
    """Return guide ids in library order."""
    return tuple(GUIDES)
