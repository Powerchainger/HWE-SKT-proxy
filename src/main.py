from zeroconf import ServiceBrowser, ServiceListener, Zeroconf, ZeroconfServiceTypes
import requests
import time
import sys
import dotenv
import os
import queue as q
import logging
import logging.handlers
import threading

dotenv.load_dotenv()

POLL_PLUG_DATA_SLEEP = 1
QUEUE_WORKER_SLEEP = 1
SMART_PLUG_CONN_ERR_SLEEP = 2
SMART_PLUG_DEVICE_NAME = "_hwenergy._tcp.local."
API_TOKEN = os.environ["API_TOKEN"]
USERID = os.environ["RASPBERRY_USER_ID"]
HOST = os.environ['API_HOST']
P1_READER_IP_ADDR = "192.168.2.17"


# Set variables locally

OWNER = os.environ['USER'] = ""
API_URL = os.environ['API_URL'] = ""
API_PORT = os.environ['API_PORT'] = ""


BUILD='0.0.2'

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

threads = []
logger = logging.getLogger(__name__)
event = threading.Event()
queue = q.Queue()
quit = False
poll = True

def send_data_to_server(measurements):
    timestamp = time.asctime(time.gmtime())
    json = {"measurements": measurements, "owner": "kevin", "timestamp": timestamp}
    logger.info("sending data to server")
    try:
        response = requests.post(f"http://shambuwu.com:8000/data/data_entry/", json=json, headers={
            "Authorization": API_TOKEN,
            "Measurement-Type": "HWE-SKT-Proxy"
        })
        logger.info(response.text)
    except requests.exceptions.ConnectionError as e:
        logger.error("error connecting to server")


def start_queue_worker():
    while not quit:
        measurements = []
        while not queue.empty():
            measurements.append(queue.get())
            event.clear()
        send_data_to_server(measurements)
        time.sleep(QUEUE_WORKER_SLEEP)
        event.set()


def poll_smart_plug_data(ipaddr, serial, event):
    while True:
        logger.info("polling smart plug data")
        try:
            r = requests.get(f"http://{ipaddr}/api/v1/data")
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.error("error fetching data from smart plug", exc_info=e)
            time.sleep(SMART_PLUG_CONN_ERR_SLEEP)
            continue   
        data = r.json()
        data["serial"] = serial
        queue.put(data)
        event.wait()


class MyListener(ServiceListener):
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        global ipaddr, quit
        try:
            info = zc.get_service_info(type_, name)
            addr = info.addresses[0]
            ipaddr = ".".join([str(b) for b in addr])
            dev_info = requests.get(f"http://{ipaddr}/api")
            json_info = dev_info.json()
            logger.info(f"Connected to smart plug with ip address: {ipaddr}")
            try:
                thread = threading.Thread(target=poll_smart_plug_data, args=(ipaddr, json_info["serial"], event))
                threads.append(thread)
            except Exception as e:
                logger.error(f"Could not start polling thread\nError message:{e}")
        except Exception as e:
            logger.exception(e)
            quit = True
            sys.exit(1)


def start_smart_plug_data_poller():
    devices = []

    while SMART_PLUG_DEVICE_NAME not in devices and not quit:
        devices = ZeroconfServiceTypes.find()
        logger.error("error connecting to smart plug")
        time.sleep(SMART_PLUG_CONN_ERR_SLEEP)

    logger.info("smart plug found, connecting..")
    # ServiceBrowser is started async
    ServiceBrowser(Zeroconf(), SMART_PLUG_DEVICE_NAME, MyListener())


def main():
#    ipaddress = P1_READER_IP_ADDR
#    thread = threading.Thread(target=poll_smart_plug_data, args=(ipaddress, "5c2faf0b84a0"))
#    threads.append(thread)
    
    start_smart_plug_data_poller()
    logger.info("Preparing queue worker...")
    time.sleep(5)
    
    for thread in threads:
        thread.start()
        
    start_queue_worker()



if __name__ == "__main__":
    main()
