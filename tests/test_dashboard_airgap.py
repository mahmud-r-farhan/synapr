"""Verify that dashboard static assets comply with the 100% local air-gap guarantee."""

from __future__ import annotations

import re
from pathlib import Path


def test_dashboard_assets_are_fully_local() -> None:
    html_path = Path("synapr/web/static/index.html")
    js_path = Path("synapr/web/static/app.js")

    assert html_path.exists(), "index.html missing"
    assert js_path.exists(), "app.js missing"

    html = html_path.read_text(encoding="utf-8")
    js = js_path.read_text(encoding="utf-8")

    remote = re.findall(r"""(?:src|href)=["'](https?:)?//[^"']+""", html)
    assert not remote, f"Dashboard must not load remote assets: {remote}"

    assert not re.search(r"""fetch\(\s*["']https?://""", js), "Dashboard must not call remote endpoints"
