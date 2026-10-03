"""Declarative host paths and launch metadata for supported editors."""

from synapr.core.models import EditorType

KNOWN_EDITORS: list[dict] = [
    {
        "id": "vscode",
        "name": "Visual Studio Code",
        "type": EditorType.VSCODE,
        "executables": ["code", "code.cmd", "code.exe"],
        "windows_paths": [
            r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe",
            r"%LOCALAPPDATA%\Programs\Microsoft VS Code\bin\code.cmd",
            r"%PROGRAMFILES%\Microsoft VS Code\Code.exe",
            r"%PROGRAMFILES%\Microsoft VS Code\bin\code.cmd",
        ],
        "mac_paths": [
            "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code",
        ],
        "linux_paths": [
            "/usr/bin/code",
            "/snap/bin/code",
        ],
        "launch_template": ["{path}"],
        "version_flag": "--version",
    },
    {
        "id": "cursor",
        "name": "Cursor AI Code Editor",
        "type": EditorType.CURSOR,
        "executables": ["cursor", "cursor.cmd", "cursor.exe"],
        "windows_paths": [
            r"%LOCALAPPDATA%\Programs\cursor\Cursor.exe",
            r"%LOCALAPPDATA%\cursor\Cursor.exe",
            r"%PROGRAMFILES%\Cursor\Cursor.exe",
        ],
        "mac_paths": [
            "/Applications/Cursor.app/Contents/MacOS/Cursor",
            "/Applications/Cursor.app/Contents/Resources/app/bin/cursor",
        ],
        "linux_paths": [
            "/usr/bin/cursor",
            "/opt/cursor/cursor",
        ],
        "launch_template": ["{path}"],
        "version_flag": "--version",
    },
    {
        "id": "windsurf",
        "name": "Windsurf Editor (Codeium)",
        "type": EditorType.WINDSURF,
        "executables": ["windsurf", "windsurf.cmd", "windsurf.exe"],
        "windows_paths": [
            r"%LOCALAPPDATA%\Programs\windsurf\Windsurf.exe",
            r"%PROGRAMFILES%\Windsurf\Windsurf.exe",
        ],
        "mac_paths": [
            "/Applications/Windsurf.app/Contents/MacOS/Windsurf",
        ],
        "linux_paths": [
            "/usr/bin/windsurf",
        ],
        "launch_template": ["{path}"],
        "version_flag": "--version",
    },
    {
        "id": "antigravity",
        "name": "AntiGravity IDE",
        "type": EditorType.ANTIGRAVITY,
        "executables": ["antigravity", "antigravity.exe", "agy", "agy.exe"],
        "windows_paths": [
            r"%LOCALAPPDATA%\Programs\AntiGravity\AntiGravity.exe",
            r"%USERPROFILE%\.gemini\antigravity-ide\bin\antigravity.exe",
        ],
        "mac_paths": [
            "/Applications/AntiGravity.app/Contents/MacOS/AntiGravity",
        ],
        "linux_paths": [
            "/usr/local/bin/antigravity",
        ],
        "launch_template": ["{path}"],
        "version_flag": "--version",
    },
    {
        "id": "android_studio",
        "name": "Android Studio",
        "type": EditorType.ANDROID_STUDIO,
        "executables": ["studio", "studio64.exe", "studio.exe", "studio.bat"],
        "windows_paths": [
            r"%PROGRAMFILES%\Android\Android Studio\bin\studio64.exe",
            r"%PROGRAMFILES%\Android\Android Studio\bin\studio.bat",
            r"%LOCALAPPDATA%\Programs\Android Studio\bin\studio64.exe",
        ],
        "mac_paths": [
            "/Applications/Android Studio.app/Contents/MacOS/studio",
        ],
        "linux_paths": [
            "/opt/android-studio/bin/studio.sh",
            "/usr/local/android-studio/bin/studio.sh",
        ],
        "launch_template": ["{path}"],
        "version_flag": "--version",
    },
    {
        "id": "intellij",
        "name": "IntelliJ IDEA",
        "type": EditorType.INTELLIJ,
        "executables": ["idea", "idea64.exe", "idea.exe"],
        "windows_paths": [
            r"%PROGRAMFILES%\JetBrains\IntelliJ IDEA Community Edition*\bin\idea64.exe",
            r"%PROGRAMFILES%\JetBrains\IntelliJ IDEA*\bin\idea64.exe",
        ],
        "mac_paths": [
            "/Applications/IntelliJ IDEA.app/Contents/MacOS/idea",
        ],
        "linux_paths": [
            "/usr/bin/idea",
            "/snap/bin/intellij-idea-community",
        ],
        "launch_template": ["{path}"],
        "version_flag": "--version",
    },
    {
        "id": "pycharm",
        "name": "PyCharm",
        "type": EditorType.PYCHARM,
        "executables": ["pycharm", "pycharm64.exe", "pycharm.exe"],
        "windows_paths": [
            r"%PROGRAMFILES%\JetBrains\PyCharm Community Edition*\bin\pycharm64.exe",
            r"%PROGRAMFILES%\JetBrains\PyCharm*\bin\pycharm64.exe",
        ],
        "mac_paths": [
            "/Applications/PyCharm.app/Contents/MacOS/pycharm",
        ],
        "linux_paths": [
            "/usr/bin/pycharm",
        ],
        "launch_template": ["{path}"],
        "version_flag": "--version",
    },
    {
        "id": "neovim",
        "name": "Neovim",
        "type": EditorType.NEOVIM,
        "executables": ["nvim", "nvim.exe"],
        "windows_paths": [
            r"%LOCALAPPDATA%\Programs\Neovim\bin\nvim.exe",
            r"%PROGRAMFILES%\Neovim\bin\nvim.exe",
        ],
        "mac_paths": [
            "/usr/local/bin/nvim",
            "/opt/homebrew/bin/nvim",
        ],
        "linux_paths": [
            "/usr/bin/nvim",
            "/snap/bin/nvim",
        ],
        "launch_template": ["{path}"],
        "version_flag": "--version",
    },
]
