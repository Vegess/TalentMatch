import importlib
import inspect
import pkgutil
from typing import Dict, Type
from app.core.plugin_interface import IngestionPlugin, RankingPlugin


class PluginLoader:
    """Singleton that discovers plugins under app.plugins.ingestion and app.plugins.ranking."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            inst = super().__new__(cls)
            inst.ingestion_plugins: Dict[str, Type[IngestionPlugin]] = {}
            inst.ranking_plugins: Dict[str, Type[RankingPlugin]] = {}
            inst._loaded = False
            cls._instance = inst
        return cls._instance

    def load_plugins(self, force: bool = False):
        if self._loaded and not force:
            return
        self._discover("app.plugins.ingestion", IngestionPlugin, self.ingestion_plugins)
        self._discover("app.plugins.ranking", RankingPlugin, self.ranking_plugins)
        self._loaded = True

    def ensure_loaded(self):
        self.load_plugins()

    def _discover(self, package_name: str, base_class: Type, registry: Dict[str, Type]):
        try:
            package = importlib.import_module(package_name)
        except Exception as e:
            print(f"Error loading plugin package {package_name}: {e}")
            return
        for _, name, _ in pkgutil.iter_modules(package.__path__):
            full_name = f"{package_name}.{name}"
            try:
                module = importlib.import_module(full_name)
            except Exception as e:  # one broken plugin must not stop the others
                print(f"Skipping plugin {full_name}: {e}")
                continue
            for cls_name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, base_class) and obj is not base_class and not inspect.isabstract(obj):
                    registry[full_name] = obj
                    print(f"Registered plugin: {cls_name} ({full_name})")
                    break

    def get_ingestion_plugin(self, name: str) -> IngestionPlugin:
        self.ensure_loaded()
        if name in self.ingestion_plugins:
            return self.ingestion_plugins[name]()
        raise ValueError(f"Ingestion plugin '{name}' not found.")

    def get_ranking_plugin(self, name: str) -> RankingPlugin:
        self.ensure_loaded()
        if name in self.ranking_plugins:
            return self.ranking_plugins[name]()
        raise ValueError(f"Ranking plugin '{name}' not found.")
