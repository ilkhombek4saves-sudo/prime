from __future__ import annotations

from app.plugins.base import PluginBase
from app.plugins.custom_api_plugin import CustomAPIPlugin
from app.plugins.deploy_plugin import DeployPlugin
from app.plugins.documentation_plugin import DocumentationPlugin
from app.plugins.slide_generator_plugin import SlideGeneratorPlugin
from app.plugins.test_plugin import TestPlugin
from app.plugins.translation_plugin import TranslationPlugin
from app.plugins.ui_code_plugin import UICodePlugin
from app.providers.base import ServiceProvider


PLUGIN_MAP: dict[str, type[PluginBase]] = {
    "deploy": DeployPlugin,
    "test": TestPlugin,
    "slides": SlideGeneratorPlugin,
    "ui_code": UICodePlugin,
    "documentation": DocumentationPlugin,
    "translation": TranslationPlugin,
    "custom_api": CustomAPIPlugin,
}


def build_plugin(plugin_name: str, provider: ServiceProvider) -> PluginBase:
    plugin_cls = PLUGIN_MAP[plugin_name]
    return plugin_cls(provider)


def list_supported_plugins() -> list[str]:
    return sorted(PLUGIN_MAP)
