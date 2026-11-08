from . import web
from .bridge import Bridge
from .fleet import Fleet
from .sap import Sap
from .vehicle import Vehicle
from .wms import Wms

PORTS = {'sap': 9004, 'wms': 9120, 'fleet': 9200, 'vehicle': 9300, 'bridge': 9090}


class Lab:
    def __init__(self, servers, bridge):
        self.servers = servers
        self.bridge = bridge
        self.urls = {name: server.url for name, server in servers.items()}

    def stop(self):
        self.bridge.stop()
        for server in self.servers.values():
            server.stop()


def start(ports=PORTS, host='127.0.0.1', step_seconds=1.0, poll_seconds=1.0):
    vehicle = Vehicle(step_seconds=step_seconds)
    services = {'sap': Sap(), 'wms': Wms(), 'fleet': Fleet(), 'vehicle': vehicle}
    servers = {name: web.serve(service.routes(), ports[name], host) for name, service in services.items()}
    bridge = Bridge(servers['sap'].url, servers['wms'].url, servers['fleet'].url, poll_seconds)
    servers['bridge'] = web.serve(bridge.routes(), ports['bridge'], host)
    vehicle.connect(servers['fleet'].url, servers['vehicle'].url)
    bridge.start()
    return Lab(servers, bridge)
