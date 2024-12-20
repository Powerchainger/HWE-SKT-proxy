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

load_dotenv()


class Config:
    POLL_PLUG_DATA_SLEEP = 1
    QUEUE_WORKER_SLEEP = 1
    SMART_PLUG_CONN_ERR_SLEEP = 2
    SMART_PLUG_DEVICE_NAME = "_hwenergy._tcp.local."
    OWNER = os.getenv('USER', "")
    WEBSOCKET_URL = os.getenv('WEBSOCKET_URL', "")


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
        self.sio = None
        self.unsent_data = []
        self.initialize_socket()

    def initialize_socket(self):
        self.sio = socketio.Client()
        self.sio.connect(Config.WEBSOCKET_URL)

        @self.sio.event
        def connect():
            self.logger.info("Connected to WebSocket server")

        @self.sio.event
        def disconnect():
            self.logger.warning("Disconnected from WebSocket server. Attempting to reconnect...")

    def run(self):
        while not self.stop_event.is_set():
            measurements = []

            while not self.data_queue.empty():
                measurements.append(self.data_queue.get())
                self.event.clear()

            if measurements:
                if self.sio.connected:
                    self.send_data_to_server(measurements)
                    if self.unsent_data:
                        self.logger.info("Sending unsent data to server")
                        self.send_data_to_server(self.unsent_data)
                        self.unsent_data.clear()
                else:
                    self.logger.warning("WebSocket server is disconnected. Measurements are being stored locally.")
                    self.unsent_data.extend(measurements)

            time.sleep(Config.QUEUE_WORKER_SLEEP)
            self.event.set()

    def send_data_to_server(self, measurements):
        max_retries = 3
        for i in range(max_retries):
            try:
                num_devices = len(measurements)
                for measurement in measurements:
                    timestamp = measurement["timestamp"]
                    wattage = measurement["active_power"]
                    serial = measurement["serial"]
                    json_data = {
                        "UserId": Config.OWNER,
                        "Timestamp": timestamp,
                        "Serial": serial,
                        "Wattage": wattage
                    }
                    # print(json_data, flush=True)
                    # self.logger.info("Sending data to server")

                    # Send data over the socket connection
                    self.sio.emit("json", json_data)
                    self.logger.info("Data sent over WebSocket")

                    with open("./measurements.csv", "a") as csv_file:
                        csv_file.write(f"{timestamp},{serial},{wattage}\n")
                self.logger.info(f"Bulk request sent to server. Contains {num_devices} devices.")
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
            while True:
                try:
                    r = requests.get(f"http://{self.ipaddr}/api/v1/data")
                    if r.ok:
                        data = r.json()
                        data["serial"] = self.serial
                        data["active_power"] = data["active_power_w"]
                        data["timestamp"] = int(time.time() * 1_000_000_000)
                        self.data_queue.put(data)
                        break
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
