from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
import requests
import time
import queue as q

queue = q.Queue()


def send_data_to_server(measurements):
    # TODO: Failure sending data to server
    # TODO: Dynamic url to differentiate between raspberries
    # TODO: API Authorization
    requests.post('http://localhost:5000/', json=measurements)
    print(measurements)


def start_queue_worker():
    while True:
        measurements = []
        while not queue.empty():
            measurements.append(queue.get())
        send_data_to_server(measurements)
        time.sleep(5)


def poll_plug_data(ipaddr):
    while True:
        # TODO: Failure fetching plug data
        r = requests.get(f"http://{ipaddr}/api/v1/data")
        data = r.json()
        data["timestamp"] = time.time()
        queue.put(data)
        time.sleep(1)


class MyListener(ServiceListener):
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        global ipaddr
        info = zc.get_service_info(type_, name)
        addr = info.addresses[0]
        ipaddr = ".".join([str(b) for b in addr])
        print("Connected to smart plug with ip address:", ipaddr)
        poll_plug_data(ipaddr)


def start_smart_plug_poller():
    # ServiceBrowser is started async
    # TODO: Connection failure to smart plug
    ServiceBrowser(Zeroconf(), "_hwenergy._tcp.local.", MyListener())


def main():
    start_smart_plug_poller()
    start_queue_worker()


if __name__ == "__main__":
    main()
