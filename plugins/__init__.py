"""
Sistema de plugins para el bot de traducción
"""
import os
import importlib
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class PluginManager:
    def __init__(self):
        self.plugins: Dict[str, Any] = {}
        self.hooks: Dict[str, List[Any]] = {}

    def load_plugins(self):
        """Cargar todos los plugins desde el directorio plugins/"""
        plugin_dir = os.path.dirname(__file__)

        for filename in os.listdir(plugin_dir):
            if filename.endswith('_plugin.py') and filename != '__init__.py':
                plugin_name = filename[:-10]  # Remover '_plugin.py'
                try:
                    module = importlib.import_module(f'plugins.{plugin_name}_plugin')
                    plugin_class = getattr(module, f'{plugin_name.title()}Plugin')
                    plugin_instance = plugin_class()
                    self.plugins[plugin_name] = plugin_instance

                    # Registrar hooks
                    if hasattr(plugin_instance, 'register_hooks'):
                        plugin_instance.register_hooks(self)

                    logger.info(f"Plugin {plugin_name} cargado exitosamente")
                except Exception as e:
                    logger.error(f"Error cargando plugin {plugin_name}: {e}")

    def register_hook(self, hook_name: str, callback):
        """Registrar un hook"""
        if hook_name not in self.hooks:
            self.hooks[hook_name] = []
        self.hooks[hook_name].append(callback)

    def execute_hook(self, hook_name: str, *args, **kwargs):
        """Ejecutar todos los callbacks registrados para un hook"""
        if hook_name in self.hooks:
            for callback in self.hooks[hook_name]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error ejecutando hook {hook_name}: {e}")

# Instancia global del plugin manager
plugin_manager = PluginManager()
