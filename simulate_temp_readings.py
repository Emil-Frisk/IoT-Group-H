import random
import time
import logging
import argparse
from logging.handlers import RotatingFileHandler
import os
import re
from azure.iot.device import IoTHubDeviceClient, Message
from azure.iot.device.exceptions import ConnectionFailedError, ConnectionDroppedError
from azure.storage.blob import BlobClient
import socket
import json

CONNECTION_STRING = os.getenv("IOTHUB_DEVICE_CONNECTION_STRING")

def store_blob(blob_info, file_name, app_logger):
    try:
        sas_url = f"https://{blob_info['hostName']}/{blob_info['containerName']}/{blob_info['blobName']}{blob_info['sasToken']}"
        with open(file_name, "rb") as data:
            blob_client = BlobClient.from_blob_url(sas_url)
            blob_client.upload_blob(data)
        return True
    except Exception as ex:
        app_logger.info(f"Unexpected error while trying to store blob: {ex}")
        return False

def upload_file(network_outage, app_logger, client):
    try:
        file_name = f"{network_outage['time_stamp']}.json"
        storage_info = client.get_storage_info_for_blob(file_name)
        
        success = store_blob(storage_info, file_name, app_logger)
        
    except Exception as ex:
        app_logger.info("Unexpected error file uploading file: {ex}")

def handle_launch_params():
    time_interval = 3
    parser = argparse.ArgumentParser()
    parser.add_argument("--time_interval", type=int, help="telemetry time interval")
    args = parser.parse_args()

    if (args.time_interval):
        time_interval = args.time_interval

    return time_interval

def setup_logging(name, filename):
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_format = format='%(asctime)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(log_format)

    # Set up file handler
    log_file = os.path.join(log_dir, filename)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1024*1024,
        backupCount=1,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)

    #setup console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # config root logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger 

def simulate_temperature():
    """Simulate temperature readings"""
    return round(random.uniform(20.0, 40.0), 2)

def simulate_humidity():
    """Simulate temperature readings"""
    return round(random.uniform(20.0, 60.0), 2)

def extract_device_id(connection_string):
    match = re.search(r'DeviceId=([^;]+);', connection_string)
    device_id = match.group(1) if match else "Not found"
    return device_id

def main():
    try:
        if not CONNECTION_STRING:
            raise ValueError("Enviroment variabel IOTHUB_DEVICE_CONNECTION_STRING is not set")

        device_id = extract_device_id(CONNECTION_STRING)

        time_interval = handle_launch_params()
        app_logger = setup_logging("application", "application.log")
        temp_logger = setup_logging("telemetry", "telemetry.log")
        alert_logger = setup_logging("alerts", "alert.log")
        error_logger = setup_logging("error", "error.log")
        
        # Create an IoT Hub client
        client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)
        app_logger.info("Device connected to IoT Hub")
        
        network_outage = {
            "time_stamp": None,
            "is_connected": True
        }

        while True:
            # Simulate temperature reading
            temperature = simulate_temperature()
            humidity = simulate_humidity()
            if (temperature > 35) :
                alert_logger.info("Temperature too high")
                
            time_stamp = time.time()

            # Create message object
            message = Message(str({
                'temperature': temperature,
                'humidity' : humidity,
                'timestamp': time_stamp,
                "device_id": device_id
            }))

            try: # Send the message
                temp_logger.info(f"Temperature {temperature} Humidity {humidity}")
                if is_network_available():
                    client = ensure_client_connection(client, app_logger)
                    if client:
                        client.send_message(message)
                        
                        ### check if there has been a network issue 
                        ### if so send the missing aggregate data to the iot-hub
                        if not network_outage["is_connected"]:
                            ### send file to iothub and delete it
                            file_path = f"{network_outage['time_stamp']}.json"
                            if os.path.exists(file_path):
                                upload_file(network_outage, app_logger, client)
                                os.remove(file_path)                       
                                app_logger.info("Network outage file has been removed")
                            else:
                                app_logger.info("Data has been lost... network outage json file not found")
                        
                        
                        network_outage["is_connected"] = True
                        time.sleep(time_interval)
                    else:
                        client.disconnect()
                        raise ConnectionError("Failed to reconnect to IoT Hub")    
                else:
                    client.disconnect()
                    raise ConnectionError("Network unavailable")
            except (ConnectionError, 
                OSError, 
                socket.gaierror, 
                TimeoutError, 
                ConnectionFailedError, 
                ConnectionDroppedError,
                ConnectionAbortedError,
                ConnectionResetError,
                ConnectionRefusedError) as e:
                
                new_message = message.data
                data = {"messages": []}
                # check if its the connection problem is a consecutive
                if network_outage["is_connected"]: # First
                    network_outage["time_stamp"] = time_stamp
                    network_outage["is_connected"] = False
                else: ## consecutive
                    file_path = f"{network_outage['time_stamp']}.json"
                    if os.path.exists(file_path):
                        try:
                            with open(file_path, "r") as file:
                                data = json.load(file)
                        except (json.JSONDecodeError, IOError) as e:
                            error_logger.info(f"Error reading JSON file: {e}. Starting with empty data.")
                    else:
                        error_logger.info(f"Data has been lost: JSON file not found creating a new one...")
                        
                data["messages"].append(new_message)
                append_network_error_msg(network_outage["time_stamp"], data, app_logger)
                time.sleep(time_interval)
            except Exception as e:
                error_logger.error(f"Unexpected error sending message: {str(e)}")
                time.sleep(time_interval)
    except ValueError as e:
        app_logger.error(f"Value error: {e}")
        client.shutdown()
    except KeyboardInterrupt:
        app_logger.log("App stopped by the user")
        client.shutdown()
    finally:
        app_logger.info("App stopped")
        client.shutdown()

def is_network_available():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False

def ensure_client_connection(client, app_logger):
    try:
        if not client.connected:
            client.shutdown()
            client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)
            client.connect()
            app_logger.info("Reconnected to IoT Hub")
        return client
    except Exception as e:
        app_logger.error(f"Failed to reconnect to IoT Hub:  {e}")
        return None

def append_network_error_msg(time_stamp, data, app_logger):
    with open(f"{time_stamp}.json", "w") as file:
        json.dump(data, file, indent=4)
        app_logger.info(f"network error json file created with time stamp : {time_stamp}")

if __name__ == "__main__":
    main()