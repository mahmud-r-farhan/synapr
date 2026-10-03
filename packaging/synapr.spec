# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

block_cipher = None
ROOT_DIR = Path(SPECPATH).resolve().parent

datas = [
    (str(ROOT_DIR / "synapr" / "web" / "static"), os.path.join("synapr", "web", "static")),
    (str(ROOT_DIR / "synapr" / "assets"), os.path.join("synapr", "assets")),
]

hiddenimports = [
    "synapr",
    "synapr.cli.main",
    "synapr.web.app",
    "synapr.orchestrator",
    "synapr.config",
    "synapr.core.config_service",
    "synapr.core.events",
    "synapr.core.http",
    "synapr.core.logger",
    "synapr.core.models",
    "synapr.discovery.detector",
    "synapr.discovery.registry",
    "synapr.dispatcher.bridge",
    "synapr.gateway.client",
    "synapr.gateway.router",
    "synapr.merger.pipeline",
    "synapr.merger.self_healing",
    "synapr.perception.screen",
    "synapr.planner.consensus",
    "synapr.planner.decomposer",
    "synapr.worktree.manager",
    "synapr.browser",
    "synapr.browser.engine",
    "synapr.browser.models",
    "synapr.browser.search",
    "synapr.email_gateway",
    "synapr.email_gateway.models",
    "synapr.email_gateway.service",
    "synapr.github",
    "synapr.github.client",
    "synapr.github.models",
    "synapr.github.service",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "starlette",
    "starlette.middleware",
    "starlette.middleware.cors",
    "starlette.staticfiles",
    "starlette.responses",
    "starlette.routing",
    "fastapi",
    "fastapi.responses",
    "fastapi.staticfiles",
    "pydantic",
    "pydantic.deprecated",
    "click",
    "colorama",
    "anyio",
]

a = Analysis(
    [str(ROOT_DIR / "synapr" / "__main__.py")],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "ruff", "mypy", "tkinter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="synapr",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT_DIR / "synapr" / "assets" / "image.ico") if os.path.exists(str(ROOT_DIR / "synapr" / "assets" / "image.ico")) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="synapr",
)
