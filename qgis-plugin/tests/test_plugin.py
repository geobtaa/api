from unittest.mock import MagicMock

from plugin import GeodataSearchPlugin


def test_plugin_init():
    iface = MagicMock()
    plugin = GeodataSearchPlugin(iface)
    assert plugin.iface == iface
    assert plugin.action is None


def test_init_gui():
    iface = MagicMock()
    plugin = GeodataSearchPlugin(iface)
    plugin.initGui()
    assert plugin.action is not None
    iface.addToolBarIcon.assert_called_once_with(plugin.action)
    iface.addPluginToMenu.assert_called_once_with("BTAA Geoportal Search", plugin.action)


def test_unload():
    iface = MagicMock()
    plugin = GeodataSearchPlugin(iface)
    plugin.initGui()

    plugin.unload()
    iface.removePluginMenu.assert_called_once_with("BTAA Geoportal Search", plugin.action)
    iface.removeToolBarIcon.assert_called_once_with(plugin.action)
