from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
import requests
import time
import queue

q = queue.Queue()


def send_data_to_server(measurements):
    requests.post('http://localhost:5000/', json=measurements)
    print(measurements)


def process_q():
    while True:
        measurements = []
        while not q.empty():
            measurements.append(q.get())
        send_data_to_server(measurements)
        time.sleep(5)


def start(ipaddr):
    print("ip address:", ipaddr)
    while True:
        r = requests.get(f"http://{ipaddr}/api/v1/data")
        data = r.json()
        data["timestamp"] = time.time()
        q.put(data)
        time.sleep(1)


class MyListener(ServiceListener):
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        global ipaddr
        info = zc.get_service_info(type_, name)
        addr = info.addresses[0]
        ipaddr = ".".join([str(b) for b in addr])
        print(ipaddr)
        start(ipaddr)


zeroconf = Zeroconf()
listener = MyListener()
browser = ServiceBrowser(zeroconf, "_hwenergy._tcp.local.", listener)
process_q()
