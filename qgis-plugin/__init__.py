def classFactory(iface):
    try:
        from .plugin import GeodataSearchPlugin
    except ImportError:
        from plugin import GeodataSearchPlugin

    return GeodataSearchPlugin(iface)
