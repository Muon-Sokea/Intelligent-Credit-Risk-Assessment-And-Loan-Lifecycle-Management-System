import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
NAV_ITEMS = (
    ("Dashboard", "Dashboard"),
    ("Loan Applications", "Application Management"),
    ("Credit Assessment", "Assessment Workspace"),
    ("Debt & Affordability", "Financial Analysis"),
    ("Loan Monitoring", "Loan Monitoring"),
    ("Banking Analytics", "Banking Analytics"),
)


class NavigationTests(unittest.TestCase):
    def test_fresh_launch_defaults_to_dashboard_and_sets_url_route(self):
        app = AppTest.from_file(str(APP_PATH)).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["active_page"], "Dashboard")
        self.assertEqual(app.query_params.get("page"), "dashboard")
        self.assertIn("Portfolio Snapshot", "\n".join(item.value for item in app.markdown))
        self.assertEqual(app.button(key="navigation-Dashboard").proto.type, "primary")

    def test_every_sidebar_page_updates_content_nav_highlight_and_route(self):
        app = AppTest.from_file(str(APP_PATH)).run()
        for page_name, content_marker in NAV_ITEMS:
            if app.session_state["active_page"] != page_name:
                app.button(key=f"navigation-{page_name}").click().run()
            self.assertFalse(app.exception, page_name)
            self.assertEqual(app.session_state["active_page"], page_name)
            self.assertEqual(app.query_params.get("page"), {
                "Dashboard": "dashboard",
                "Loan Applications": "loan-applications",
                "Credit Assessment": "credit-assessment",
                "Debt & Affordability": "debt-affordability",
                "Loan Monitoring": "loan-monitoring",
                "Banking Analytics": "banking-analytics",
            }[page_name])
            rendered = "\n".join(item.value for item in app.markdown)
            self.assertIn(content_marker, rendered)
            self.assertIn(f'<div class="page-heading">{page_name}</div>', rendered)
            self.assertEqual(app.button(key=f"navigation-{page_name}").proto.type, "primary")

    def test_direct_url_refresh_and_browser_back_restore_selected_page(self):
        app = AppTest.from_file(str(APP_PATH))
        app.query_params["page"] = "loan-monitoring"
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["active_page"], "Loan Monitoring")
        self.assertIn("Loan Monitoring", "\n".join(item.value for item in app.markdown))

        app.button(key="navigation-Banking Analytics").click().run()
        self.assertEqual(app.session_state["active_page"], "Banking Analytics")
        app.query_params["page"] = "loan-monitoring"
        app.run()
        self.assertEqual(app.session_state["active_page"], "Loan Monitoring")
        self.assertFalse(app.exception)

    def test_application_records_survive_page_switches_and_sidebar_collapse(self):
        app = AppTest.from_file(str(APP_PATH)).run()
        app.button(key="navigation-Loan Applications").click().run()
        app.session_state["loan_application_records"][0]["navigation_test_marker"] = "kept"
        app.button(key="navigation-Credit Assessment").click().run()
        app.button(key="navigation-Loan Applications").click().run()
        self.assertEqual(app.session_state["loan_application_records"][0]["navigation_test_marker"], "kept")

        self.assertEqual(app.button(key="navigation-Loan Applications").help, "")
        app.button(key="sidebar-toggle").click().run()
        self.assertTrue(app.session_state["sidebar_collapsed"])
        self.assertEqual(app.button(key="navigation-Loan Applications").help, "Loan Applications")
        app.button(key="navigation-Credit Assessment").click().run()
        self.assertEqual(app.session_state["active_page"], "Credit Assessment")
        app.button(key="sidebar-toggle").click().run()
        self.assertFalse(app.session_state["sidebar_collapsed"])
        self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
