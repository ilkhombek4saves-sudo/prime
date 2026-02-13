import pytest

from app.plugins.deploy_plugin import DeployPlugin
from app.providers.shell_provider import ShellProvider


def test_deploy_plugin_requires_admin():
    provider = ShellProvider(name="shell", config={"allowed_scripts": ["deploy.sh"]})
    plugin = DeployPlugin(provider)

    with pytest.raises(Exception):
        plugin.check_permissions("user")
