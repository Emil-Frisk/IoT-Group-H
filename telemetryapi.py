import azure.functions as func
from azure.storage.blob import BlobServiceClient
import logging
import json
import base64
from ast import literal_eval
import os
import datetime
from collections import defaultdict

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

def group_timestamps_by_hour(device_data):
    hourly_groups = defaultdict(list)
    for data in device_data:
        if isinstance(data["timestamp"], (int, float)):
            dt = datetime.datetime.fromtimestamp(data["timestamp"])
            hour_start = dt.replace(minute=0, second=0, microsecond=0)
            hour_start_ts = hour_start.timestamp()
            hourly_groups[hour_start_ts].append(data)
    return hourly_groups

def create_hourly_avg(results):
    hourly_averages = {}
    
    for device_id, device_data in results.items():
        # Group this device's data by hour
        hourly_groups = group_timestamps_by_hour(device_data)
        device_averages = []
        
        for hour_ts, hour_data in hourly_groups.items():
            total_temp = 0.0
            total_hum = 0.0
            count_temp = 0
            count_hum = 0
            
            for data in hour_data:
                if data["temperature"] != 'N/A':
                    total_temp += float(data["temperature"])
                    count_temp += 1
                if data["humidity"] != 'N/A':
                    total_hum += float(data["humidity"])
                    count_hum += 1
            
            avg_temp = total_temp / count_temp if count_temp > 0 else 'N/A'
            avg_hum = total_hum / count_hum if count_hum > 0 else 'N/A'
            
            device_averages.append({
                "hour_start": datetime.datetime.fromtimestamp(hour_ts).isoformat(),
                "avg_temperature": avg_temp,
                "avg_humidity": avg_hum,
                "data_points": len(hour_data)
            })
        
        if device_averages:
            hourly_averages[device_id] = device_averages
    
    return hourly_averages

@app.route(route="http_trigger")
def http_trigger(req: func.HttpRequest):
    logging.info('Python HTTP trigger function processed a request.')

    # Get query parameter 'avg'
    avg_param = req.params.get('avg', 'no').lower()
    device_id_param = req.params.get("device_id", None)
    device_id_filter = device_id_param.lower() if device_id_param else None

    connection_string = os.getenv("HotstorageConnectionString")
    if not connection_string:
        return func.HttpResponse("Storage connection string not found", status_code=500)

    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client("telemetry")
    results = defaultdict(list)

    blob_list = container_client.list_blobs(name_starts_with="")
    for page in blob_list.by_page():
        for blob in page:
            logging.info(f"Blob found: {blob.name}")
            if blob.name.endswith('.json'):
                logging.info(f"Processing blob: {blob.name}")
                blob_client = container_client.get_blob_client(blob.name)
                try:
                    blob_data = blob_client.download_blob().readall()
                    blob_content = blob_data.decode("utf-8")
                    lines = blob_content.splitlines()
                    for line_num, line in enumerate(lines, 1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            json_data = json.loads(line)
                        except json.JSONDecodeError as je:
                            logging.error(f"Invalid JSON in {blob.name}, line {line_num}: {str(je)}, content: {line[:500]}")
                            continue

                        body_encoded = json_data.get("Body", "")
                        if body_encoded:
                            body_bytes = base64.b64decode(body_encoded)
                            body_dict = literal_eval(body_bytes.decode('utf-8'))
                            temperature = body_dict.get("temperature", 'N/A')
                            humidity = body_dict.get("humidity", 'N/A')
                            timestamp = body_dict.get("timestamp", 'N/A')
                            device_id = body_dict.get("device_id", 'N/A')
                            
                            logging.info(f"Processing blob with device id: {device_id}")
                            
                            if device_id_filter and device_id_filter != device_id:
                                continue
                            
                            # Ensure timestamp is a number for grouping
                            if isinstance(timestamp, (int, float)):
                                results[device_id].append({
                                    "blob_name": blob.name,
                                    "temperature": temperature,
                                    "humidity": humidity,
                                    "timestamp": timestamp
                                })
                            else:
                                logging.warning(f"Invalid timestamp in {blob.name}")

                        else:
                            logging.warning(f"No body field in {blob.name}")

                except json.JSONDecodeError:
                    logging.error(f"Invalid JSON in {blob.name}")
                except Exception as e:
                    logging.error(f"Error processing {blob.name}: {str(e)}")
            else:
                logging.warning("Found a blob with no .json")

    # Check if avg=yes and process hourly averages
    if avg_param == 'yes':
        response_data = create_hourly_avg(results)
        response = {
            "total_devices_processed": len(response_data),
            "data": response_data
        }
    else:
        # Convert defaultdict to regular dict for JSON serialization
        response_data = dict(results)
        response = {
            "total_devices_processed": len(response_data),
            "data": response_data
        }

    return func.HttpResponse(
        json.dumps(response, default=str),
        mimetype="application/json",
        status_code=200
    )