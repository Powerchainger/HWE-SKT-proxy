from zeroconf import ServiceBrowser, ServiceListener, Zeroconf, ZeroconfServiceTypes
import requests
import time
import sys
import queue as q
import logging
import logging.handlers

POLL_PLUG_DATA_SLEEP = 1
QUEUE_WORKER_SLEEP = 1
SOCKET_CONN_ERR_SLEEP = 2
SOCKET_DEVICE_NAME = "_hwenergy._tcp.local."

logging.basicConfig(
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            'proxy.log',
            maxBytes=10240000,
            backupCount=5
        )
    ],
    level=logging.INFO,
    format='%(asctime)s %(levelname)s PID_%(process)d %(message)s'
)

logger = logging.getLogger(__name__)
queue = q.Queue()
quit = False


def send_data_to_server(measurements):
    # TODO: Dynamic url to differentiate between raspberries
    # TODO: API Authorization
    logger.info("sending data to server")
    try:
        requests.post('http://localhost:5000/', json=measurements, headers={
            "Authorization": "secret"
        })
    except requests.exceptions.ConnectionError as e:
        logger.error("error connecting to server", exc_info=e)


def start_queue_worker():
    while not quit:
        measurements = []
        while not queue.empty():
            measurements.append(queue.get())
        send_data_to_server(measurements)
        time.sleep(QUEUE_WORKER_SLEEP)


def poll_socket_data(ipaddr):
    while True:
        logger.info("polling socket data")
        try:
            r = requests.get(f"http://{ipaddr}/api/v1/data")
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.error("error fetching data from socket", exc_info=e)
            time.sleep(SOCKET_CONN_ERR_SLEEP)
            continue
        data = r.json()
        logger.info(f"received: {data}")
        data["timestamp"] = time.time()
        queue.put(data)
        time.sleep(POLL_PLUG_DATA_SLEEP)


class MyListener(ServiceListener):
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        global ipaddr, quit
        try:
            info = zc.get_service_info(type_, name)
            addr = info.addresses[0]
            ipaddr = ".".join([str(b) for b in addr])
            logger.info(f"Connected to smart plug with ip address: {ipaddr}")
            poll_socket_data(ipaddr)
        except Exception as e:
            logger.exception(e)
            quit = True
            sys.exit(1)


def start_socket_data_poller():
    devices = []

    while SOCKET_DEVICE_NAME not in devices and not quit:
        devices = ZeroconfServiceTypes.find()
        logger.error("error connecting to socket")
        time.sleep(SOCKET_CONN_ERR_SLEEP)

    logger.info("socket found, connecting..")
    # ServiceBrowser is started async
    ServiceBrowser(Zeroconf(), SOCKET_DEVICE_NAME, MyListener())


def main():
    start_socket_data_poller()
    start_queue_worker()


if __name__ == "__main__":
    main()
