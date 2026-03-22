def classFactory(iface):
    from .plugin import GeodataSearchPlugin
    return GeodataSearchPlugin(iface)