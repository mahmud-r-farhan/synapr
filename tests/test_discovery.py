"""Unit tests for Host Environment and IDE discovery."""

from synapr.core.models import EditorInfo, EditorType
from synapr.discovery.detector import EditorDetector
from synapr.discovery.registry import EditorRegistry


def test_detector_discovery() -> None:
    """Test standard discovery without crashing."""
    detector = EditorDetector()
    discovered = detector.discover_all()
    assert isinstance(discovered, list)
    # Check that at least some editors were identified or checked
    for ed in discovered:
        assert ed.id
        assert ed.executable_path


def test_registry_registration() -> None:
    """Test custom editor registration and resolution."""
    registry = EditorRegistry()
    custom_editor = EditorInfo(
        id="my-custom-ide",
        name="Custom AI Studio",
        editor_type=EditorType.CUSTOM,
        executable_path="dummy-path",
        is_available=True,
    )
    registry.register_custom(custom_editor)

    fetched = registry.get_editor("my-custom-ide")
    assert fetched is not None
    assert fetched.name == "Custom AI Studio"


def test_resolve_best_editor() -> None:
    """Test heuristic editor resolution."""
    registry = EditorRegistry()
    best = registry.resolve_best_editor(
        requested="non-existent-editor",
        task_tags=["backend", "python"],
        file_scopes=["src/api.py"],
    )
    assert best is not None
    assert best.id
