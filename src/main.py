import os
import time
import queue
import threading
import requests
import logging
import logging.handlers
import json
import socketio
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf, ZeroconfServiceTypes
from dotenv import load_dotenv
from datetime import datetime

@sio.event
def connect():
    print("Connected to the server")
    # You can log successful connections here, or trigger actions

@sio.event
def disconnect():
    print("Disconnected from the server")

load_dotenv()

class Config:
    POLL_PLUG_DATA_SLEEP = 1
    QUEUE_WORKER_SLEEP = 1
    SMART_PLUG_CONN_ERR_SLEEP = 2
    SMART_PLUG_DEVICE_NAME = "_hwenergy._tcp.local."
    API_TOKEN = os.getenv("API_TOKEN")
    USERID = os.getenv("USER_ID")
    HOST = os.getenv('API_HOST')
    P1_READER_IP_ADDR = "192.168.2.17"
    OWNER = os.getenv('USER', "")
    API_URL = os.getenv('API_URL', "")
    API_PORT = os.getenv('API_PORT', "")

class Logger:
    def __init__(self):
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
        self.logger = logging.getLogger(__name__)

def is_connected():
    try:
        requests.get("http://www.google.com", timeout=5)
        return True
    except requests.ConnectionError:
        return False


class QueueWorker(threading.Thread):
    def __init__(self, data_queue, event, stop_event):
        super().__init__()
        self.data_queue = data_queue
        self.event = event
        self.stop_event = stop_event
        self.logger = Logger().logger

    def run(self):
        while not self.stop_event.is_set():
            measurements = []

            while not self.data_queue.empty():
                measurements.append(self.data_queue.get())
                self.event.clear()

            if measurements:
                self.send_data_to_server(measurements)

            time.sleep(Config.QUEUE_WORKER_SLEEP)
            self.event.set()
    
    def send_data_to_server(self, measurements):
        max_retries = 3
        for i in range(max_retries):
            try:
                for measurement in measurements:
                    timestamp = int(time.time())
                    wattage = measurement["active_power"]
                    serial = measurement["serial"]
                    json_data = {
                        "UserId": Config.USERID,
                        "Timestamp": timestamp,
                        "Wattage": wattage
                    }
                    print(json_data, flush=True)
                    self.logger.info("Sending data to server")
                    response = requests.post(f"https://demo.powerchainger.nl/api", 
                                             data=json.dumps(json_data), 
                                             headers={"Content-Type": "application/json"})

                    with open("./measurements.csv", "a") as csv_file:
                        csv_file.write(f"{timestamp},{serial},{wattage}\n")

                    if response.ok:
                        self.logger.info(response.text)
                    else:
                        self.logger.error(f"Server returned {response.status_code}: {response.text}")
                break
            except requests.exceptions.ConnectionError:
                self.logger.error("Lost connection to server. Retrying in 5 seconds.")
                time.sleep(5)

class SmartPlugPoller(threading.Thread):
    def __init__(self, ipaddr, serial, event, data_queue):
        super().__init__()
        self.ipaddr = ipaddr
        self.serial = serial
        self.event = event
        self.data_queue = data_queue
        self.logger = Logger().logger

    def run(self):
        while not self.event.is_set():
            try:
                r = requests.get(f"http://{self.ipaddr}/api/v1/data")
                if r.ok:
                    data = r.json()
                    data["serial"] = self.serial
                    data["active_power"] = data["active_power_w"]
                    self.data_queue.put(data)
                else:
                    self.logger.error(f"Smart plug returned {r.status_code}: {r.text}")
            except requests.exceptions.ConnectionError:
                self.logger.error("Lost connection to smart plug. Retrying in 5 seconds.")
                time.sleep(5)

            time.sleep(Config.POLL_PLUG_DATA_SLEEP)

class ServiceListenerImpl(ServiceListener):
    def __init__(self, threads, stop_event, data_queue):
        self.threads = threads
        self.stop_event = stop_event
        self.data_queue = data_queue
        self.logger = Logger().logger

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        try:
            info = zc.get_service_info(type_, name)
            addr = info.addresses[0]
            ipaddr = '.'.join(map(str, addr))
            dev_info = requests.get(f"http://{ipaddr}/api")
            if dev_info.ok:
                json_info = dev_info.json()
                if json_info["serial"] not in self.threads:
                    thread = SmartPlugPoller(ipaddr, json_info["serial"], self.stop_event, self.data_queue)
                    self.threads[json_info["serial"]] = thread
                    self.logger.info(f"Connected to smart plug with ip address: {ipaddr}")
            else:
                self.logger.error(f"Device info request returned {dev_info.status_code}: {dev_info.text}")
        except Exception as e:
            self.logger.exception(e)
            self.stop_event.set()

def main():
    logger = Logger().logger
    stop_event = threading.Event()
    threads = {}
    data_queue = queue.Queue()

    try:
        with Zeroconf() as zeroconf:
            listener = ServiceListenerImpl(threads, stop_event, data_queue)
            ServiceBrowser(zeroconf, Config.SMART_PLUG_DEVICE_NAME, listener)
            logger.info("Preparing queue worker...")
            time.sleep(8)
            
            for thread in threads.values():
                thread.start()

            queue_worker = QueueWorker(data_queue, threading.Event(), stop_event)
            queue_worker.start()

            while not stop_event.is_set():
                time.sleep(1)
    except Exception as e:
        logger.exception(e)
    finally:
        stop_event.set()
        for thread in threads.values():
            thread.join()

if __name__ == "__main__":
    main()

