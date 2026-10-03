"""Editor registry for resolving, querying, and managing editor profiles."""


from synapr.core.logger import logger
from synapr.core.models import EditorInfo, EditorType
from synapr.discovery.detector import EditorDetector


class EditorRegistry:
    """Registry maintaining available editors and mapping tasks to optimal tools."""

    def __init__(self, detector: EditorDetector | None = None) -> None:
        self.detector = detector or EditorDetector()
        self._editors: dict[str, EditorInfo] = {}
        self._refresh()

    def _refresh(self) -> None:
        """Scan and populate the registry."""
        items = self.detector.discover_all()
        self._editors = {e.id: e for e in items}

    def refresh(self) -> list[EditorInfo]:
        """Re-scan the host machine and return the refreshed editor list."""
        self._refresh()
        return self.list_available()

    def list_available(self) -> list[EditorInfo]:
        """Return all discovered and available editors."""
        return list(self._editors.values())

    def get_editor(self, editor_id: str) -> EditorInfo | None:
        """Fetch editor info by identifier."""
        if editor_id in self._editors:
            return self._editors[editor_id]
        # Attempt just-in-time discovery for custom binaries
        found = self.detector.find_editor(editor_id)
        if found:
            self._editors[found.id] = found
            return found
        return None

    def register_custom(self, editor_info: EditorInfo) -> None:
        """Register a user-defined custom editor profile."""
        self._editors[editor_info.id] = editor_info
        logger.info(f"Registered custom editor: {editor_info.id} ({editor_info.executable_path})")

    def resolve_best_editor(
        self,
        requested: str | None = None,
        task_tags: list[str] | None = None,
        file_scopes: list[str] | None = None,
    ) -> EditorInfo:
        """Resolve the best editor for a given task, falling back gracefully."""
        # 1. Exact match requested
        if requested and requested in self._editors:
            return self._editors[requested]

        # 2. Check task tags or file extensions
        tags = [t.lower() for t in (task_tags or [])]
        scopes = [s.lower() for s in (file_scopes or [])]

        is_android = any(
            "android" in t or "kotlin" in t or s.endswith((".kt", ".java", ".gradle"))
            for t in tags for s in scopes
        )
        if is_android and "android_studio" in self._editors:
            return self._editors["android_studio"]

        # 3. Preference ranking: cursor -> windsurf -> vscode -> any available
        priority = ["cursor", "windsurf", "vscode", "antigravity", "neovim", "intellij", "pycharm"]
        for p in priority:
            if p in self._editors:
                return self._editors[p]

        # 4. If any editor is registered at all
        if self._editors:
            return next(iter(self._editors.values()))

        # 5. Fallback placeholder for air-gapped systems with no GUI editor in PATH
        return EditorInfo(
            id="cli-fallback",
            name="System Terminal",
            editor_type=EditorType.CUSTOM,
            executable_path="cmd.exe",
            is_available=True,
            launch_args_template=["/c", "echo", "Working in: {path}"],
        )
