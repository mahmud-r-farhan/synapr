"""Import command modules to register them on the shared Click group."""

from importlib import import_module

for _module in ("core", "config", "research", "github", "mail", "dashboard"):
    import_module(f"{__name__}.{_module}")
