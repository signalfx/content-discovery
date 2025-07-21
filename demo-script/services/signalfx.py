import os
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logger = logging.getLogger(__name__)

# Log message constants
CREATED_DASHBOARD_GROUP = "✅ Created dashboard group: %s"
FAILED_DASHBOARD_GROUP = "❌ Failed to create dashboard group: %s"

FETCH_DASHBOARD_FAILED = "❌ Failed to fetch dashboard (%s): %s"

CREATED_CHART = "✅ Created chart: %s (ID: %s)"
FAILED_CHART = "❌ Failed to create chart: %s"

MISSING_DASHBOARD_ID = "❌ Dashboard ID missing"
CHART_ADDED_TO_DASHBOARD = "✅ Added chart to dashboard ID: %s"
FAILED_TO_ADD_CHART = "❌ Failed to add chart to dashboard: %s"

DRY_RUN_SKIPPED = "🔍 Dry run - chart creation skipped: %s"
CHART_PLACED = "📌 Chart '%s' added at row %d, column %d"
ALL_CHARTS_PROCESSED = "✅ All charts processed for dashboard ID: %s"

FAILED_DASHBOARD_DETAILS = "❌ Failed to get dashboard details for ID: %s"


class SignalFxClient:
    """
    A manager class for interacting with SignalFx dashboard and chart APIs.
    Provides methods to create dashboard groups, charts, and update dashboards with charts.
    """

    def __init__(self, base_url=None, org_id=None, api_token=None):
        """
        Initialize the SignalFxDashboardManager.

        Args:
            base_url (str, optional): Override for SIGNALFX_BASE_URL.
            org_id (str, optional): Override for SIGNALFX_ORG_ID.
            api_token (str, optional): Override for SIGNALFX_API_TOKEN.

        Raises:
            EnvironmentError: If required environment variables are missing.
        """
        self.base_url = base_url or os.getenv("SIGNALFX_BASE_URL")
        self.org_id = org_id or os.getenv("SIGNALFX_ORG_ID")
        self.api_token = api_token or os.getenv("SIGNALFX_API_TOKEN")

        for var_name, var_value in {
            "SIGNALFX_BASE_URL": self.base_url,
            "SIGNALFX_ORG_ID": self.org_id,
            "SIGNALFX_API_TOKEN": self.api_token,
        }.items():
            if not var_value:
                raise EnvironmentError(f"Missing required environment variable: {var_name}")

        self.session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.headers = {
            "X-SF-TOKEN": self.api_token,
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json",
            "X-SF-SOURCE": "signalview",
        }

    def _build_url(self, path: str) -> str:
        """
        Helper method to construct full API URL with org ID.

        Args:
            path (str): API path (e.g., '/v2/chart').

        Returns:
            str: Full URL with organization ID.
        """
        return f"{self.base_url}{path}?organizationId={self.org_id}"

    def create_dashboard_group(self, name: str, description: str):
        """
        Create a new dashboard group in SignalFx.

        Args:
            name (str): Name of the dashboard group.
            description (str): Description of the dashboard group.

        Returns:
            dict or None: JSON response of created dashboard group, or None on failure.
        """
        url = self._build_url("/v2/dashboardgroup")
        payload = {
            "name": name,
            "description": description,
            "permissions": {
                "acl": [
                    {
                        "principalId": self.org_id,
                        "principalType": "ORG",
                        "actions": ["READ", "WRITE"],
                    }
                ],
                "parent": None,
            },
        }

        response = self.session.post(url, headers=self.headers, json=payload)
        if response.ok:
            logger.info(CREATED_DASHBOARD_GROUP, name)
            return response.json()
        logger.error(FAILED_DASHBOARD_GROUP, response.text)
        return None

    def get_dashboard(self, dashboard_id: str):
        """
        Retrieve a specific dashboard by ID.

        Args:
            dashboard_id (str): ID of the dashboard.

        Returns:
            dict or None: Dashboard JSON data or None on failure.
        """
        url = self._build_url(f"/v2/dashboard/{dashboard_id}")
        response = self.session.get(url, headers=self.headers)

        if response.ok:
            return response.json()
        logger.error(FETCH_DASHBOARD_FAILED, dashboard_id, response.text)
        return None

    def create_chart(self, chart_json: dict):
        """
        Create a new chart in SignalFx.

        Args:
            chart_json (dict): JSON payload for the chart definition.

        Returns:
            dict or None: Created chart data or None on failure.
        """
        url = self._build_url("/v2/chart")
        response = self.session.post(url, headers=self.headers, json=chart_json)

        if response.ok:
            chart = response.json()
            logger.info(CREATED_CHART, chart.get("name"), chart.get("id"))
            return chart
        logger.error(FAILED_CHART, response.text)
        return None

    def add_chart_to_dashboard(self, dashboard_id: str, new_chart_entry: dict):
        """
        Add a chart to a given dashboard's chart list.

        Args:
            dashboard (str): Dashboard id.
            new_chart_entry (dict): Chart positioning and ID details.

        Returns:
            dict or None: Updated dashboard JSON or None on failure.
        """
        dashboard_data = self.get_dashboard(dashboard_id)
        if not dashboard_data:
            logger.error(FAILED_DASHBOARD_DETAILS, dashboard_id)
            return
        
        dashboard_id = dashboard_data.get("id")
        if not dashboard_id:
            logger.error(MISSING_DASHBOARD_ID)
            return None

        url = self._build_url(f"/v2/dashboard/{dashboard_id}")
        dashboard_data.setdefault("charts", []).append(new_chart_entry)

        response = self.session.put(url, headers=self.headers, json=dashboard_data)
        if response.ok:
            logger.info(CHART_ADDED_TO_DASHBOARD, dashboard_id)
            return response.json()
        logger.error(FAILED_TO_ADD_CHART, response.text)
        return None

    def add_chart_list_to_dashboard(self, dashboard_id: str, chart_list: list, dry_run=False):
        """
        Add a list of charts to a dashboard, arranging them in a grid layout.

        Args:
            dashboard_id (str): ID of the target dashboard.
            chart_list (list): List of chart JSON definitions.
            dry_run (bool): If True, charts are not created or added.

        Returns:
            None
        """
        dashboard_data = self.get_dashboard(dashboard_id)
        if not dashboard_data:
            logger.error(FAILED_DASHBOARD_DETAILS, dashboard_id)
            return

        row, column = 0, 0

        for chart_json in chart_list:
            if dry_run:
                logger.info(DRY_RUN_SKIPPED, chart_json.get("name"))
                continue

            created_chart = self.create_chart(chart_json)
            if not created_chart:
                continue

            chart_entry = {
                "chartId": created_chart["id"],
                "column": column,
                "row": row,
                "height": 1,
                "width": 6,
            }

            if self.add_chart_to_dashboard(dashboard_data, chart_entry):
                logger.info(CHART_PLACED, created_chart.get("name"), row, column)

            column += 6
            if column >= 12:
                column = 0
                row += 1

        logger.info(ALL_CHARTS_PROCESSED, dashboard_id)
