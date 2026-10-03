"""Integrations environment variable declarations."""

from .env_types import EnvVarSpec

SPECS: tuple[EnvVarSpec, ...] = (
    EnvVarSpec(
        name="SYNAPR_UI_HOST",
        path="ui.host",
        description="Bind address of the local dashboard.",
        example="127.0.0.1",
    ),
    EnvVarSpec(
        name="SYNAPR_UI_PORT",
        path="ui.port",
        kind="int",
        description="TCP port of the local dashboard.",
        example="8765",
    ),
    EnvVarSpec(
        name="SYNAPR_UI_OPEN_BROWSER",
        path="ui.auto_open_browser",
        kind="bool",
        description="Open the default browser when the dashboard starts.",
        example="true",
    ),
    EnvVarSpec(
        name="SYNAPR_UI_ALLOW_CONFIG_WRITES",
        path="ui.allow_config_writes",
        kind="bool",
        description="Allow the dashboard to edit and persist the configuration.",
        example="true",
    ),
    EnvVarSpec(
        name="SYNAPR_UI_ALLOW_REMOTE_ORIGINS",
        path="ui.allow_remote_origins",
        kind="bool",
        description="Relax CORS so non-localhost origins may call the API.",
        example="false",
    ),
    EnvVarSpec(
        name="SYNAPR_UI_REFRESH_SECONDS",
        path="ui.refresh_interval_seconds",
        kind="float",
        description="Dashboard polling interval for status widgets.",
        example="5",
    ),
    EnvVarSpec(
        name="SYNAPR_SEARCH_ENGINE",
        path="browser.search_engine",
        description="Search engine backend (duckduckgo, searxng).",
        example="duckduckgo",
    ),
    EnvVarSpec(
        name="SYNAPR_SEARXNG_URL",
        path="browser.searxng_url",
        description="SearXNG endpoint URL.",
        example="http://localhost:8080",
    ),
    EnvVarSpec(
        name="SYNAPR_MAX_SEARCH_RESULTS",
        path="browser.max_search_results",
        kind="int",
        description="Maximum search results to retrieve.",
        example="5",
    ),
    EnvVarSpec(
        name="SYNAPR_EMAIL_ENABLED",
        path="email.enabled",
        kind="bool",
        description="Enable email triage gateway.",
        example="true",
    ),
    EnvVarSpec(
        name="SYNAPR_IMAP_HOST",
        path="email.imap_host",
        description="IMAP server hostname.",
        example="imap.example.com",
    ),
    EnvVarSpec(
        name="SYNAPR_IMAP_USERNAME",
        path="email.imap_username",
        description="IMAP username / email.",
        example="dev@example.com",
    ),
    EnvVarSpec(
        name="SYNAPR_IMAP_PASSWORD",
        path="email.imap_password",
        secret=True,
        description="IMAP password or app token.",
        example="secret_token",
    ),
    EnvVarSpec(
        name="SYNAPR_GITHUB_TOKEN",
        path="github.token",
        secret=True,
        aliases=("GITHUB_TOKEN", "GH_TOKEN"),
        description="GitHub personal access token.",
        example="ghp_live_secret",
    ),
    EnvVarSpec(
        name="SYNAPR_GITHUB_REPO",
        path="github.repository",
        description="Target GitHub repository (owner/repo).",
        example="mahmud-r-farhan/synapr",
    )
)
