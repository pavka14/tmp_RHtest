import logging
import time

import psutil
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from config import *

logging.basicConfig(
    filename="alerts.log",
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def get_system_metrics():
    """Collects basic telemetry from the host system."""
    # Get CPU usage percentage. percpu=True will break it down per core, with percpu=False we get overall usage.
    cpu_usage_overall = psutil.cpu_percent(interval=1, percpu=False)
    cpu_usage = psutil.cpu_percent(interval=1, percpu=True)

    # Get memory usage.
    memory_info = psutil.virtual_memory()
    memory_usage = memory_info.percent

    # Get disk I/O statistics.
    disk_io = psutil.disk_io_counters()
    disk_read = disk_io.read_bytes
    disk_write = disk_io.write_bytes

    # Get network I/O statistics. These are incremental, so in this form probably not too useful.
    network_io = psutil.net_io_counters()
    network_sent = network_io.bytes_sent
    network_recv = network_io.bytes_recv

    # These names need to be defined as constants somewhere, to enforce consistency.
    collected_metrics = {
        "cpu_usage_overall": cpu_usage_overall,
        "cpu_usage": cpu_usage,
        "memory_usage": memory_usage,
        "disk_read": disk_read,
        "disk_write": disk_write,
        "network_sent": network_sent,
        "network_recv": network_recv,
    }

    if VERBOSE:
        print("System Metrics:")
        for key, value in collected_metrics.items():
            print(f"{key}: {value}")

    return collected_metrics


def try_to_clear_buffer():
    """Properly, this should work in a separate process, but to avoid clutter it is now called inside the main process
    which runs every 10 seconds."""
    if len(buffer) > 0:
        # Modifying a list while iterating over it is extremely dodgy, so we iterate over a shallow copy of the buffer.
        for saved_point in buffer[:]:
            if VERBOSE:
                print(f"Trying to save buffered data point to DB: {saved_point}")
            try:
                write_api.write(
                    bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=saved_point
                )
                buffer.remove(saved_point)
                if VERBOSE:
                    print(
                        f"Saved buffered data point to DB, buffer remaining size: {len(buffer)}"
                    )
            except Exception as e:
                logging.warning(f"InfluxDB write failed: {e}")
                # If it failed, there is no point continuing the loop through the buffer, only to fail again and again.
                return


def write_metrics_to_influxdb():
    """Write one data point to InfluxDB.
    If it works, also try to clear the buffer 9if any)."""
    timestamp = int(time.time())
    # The default is to not send a time value, and then InfluxDB will record the measurement as "now".
    # However, you cannot save back-dated data that way.
    # TODO This needs some investigating, it seems to have trouble with times at .00 seconds.
    point = Point("system_metrics").tag("server", "1").time(timestamp, WritePrecision.S)
    for field, value in metrics.items():
        if isinstance(value, list):
            # Handle lists by creating subfields with an index; this is needed e.g. when the CPU has more than one core:
            # the psutil query above will return a list.
            for idx, sub_value in enumerate(value):
                point.field(f"{field}_{idx + 1}", sub_value)
        else:
            point.field(field, value)

    try:
        write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
        if VERBOSE:
            print("InfluxDB write successful")
        # If it worked, this is the time to try and clear the buffer (if any); if it fails, no point trying.
        try_to_clear_buffer()
    except Exception as e:
        logging.warning(f"InfluxDB write failed: {e}")
        print(f"InfluxDB write failed: {e}")
        if len(buffer) < BUFFER_SIZE:
            buffer.append(point)
            print(f"Data point added to buffer. Current buffer size: {len(buffer)}")
        else:
            print(
                f"Buffer has reached size limit: {len(buffer)}, discarding data point."
            )
            # At least save the data point to the log, for possible future retrieval.
            # This seems to not save the custom timestamp added, so will need some more work.
            logging.warning(f"Data point not saved to DB: {point}")


def get_average_cpu_load(alert_period: int):
    """Used by the process which triggers an alert if CPU load is above a pre-set value.
    Data comes from the InfluxDB storage."""
    query = f"""
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: -{alert_period}m)
      |> filter(fn: (r) => r._measurement == "system_metrics" and r._field == "cpu_usage_overall")
      |> mean()
    """
    result = query_api.query(org=INFLUXDB_ORG, query=query)

    for table in result:
        for record in table.records:
            # The way the query is structured, there will be exactly one value, so just return it here.
            return record.get_value()

    return None


def check_if_cpu_alert_needed(alert_check):
    """Checks if CPU alert is needed, and if the condition is met saves an alert in the log.
    In a real environment, the alert would go elsewhere.
    This raises an alert every time the condition is met"""
    alert_period, alert_value = alert_check
    try:
        average_cpu_load = get_average_cpu_load(alert_period=alert_period)
    except Exception as e:
        if VERBOSE:
            print(f"Could not check average CPU load : {e}")
        logging.warning(f"Could not check average CPU load : {e}")
        return

    if VERBOSE:
        print(f"Average CPU load for last {alert_period} minutes: {average_cpu_load}")

    if average_cpu_load > alert_value:
        message = f"Average CPU load {average_cpu_load:.2f} for last {alert_period} minutes exceeds {alert_value}"
        if VERBOSE:
            print(message)
        logging.warning(message)


def check_alerts():
    """Properly, this should work in a separate process, but to avoid clutter it is now called inside the main process
    which runs every 10 seconds."""
    for alert_name, alert_check in ALERTS.items():
        # This will need to be generalised for actual usage, with the ALERTS list defined to have the name of the
        # function that is to run - then there will be no need for any "if" statements.
        if alert_name == "cpu_usage_overall":
            if VERBOSE:
                print("Checking cpu_usage_overall.")
        check_if_cpu_alert_needed(alert_check)


if __name__ == "__main__":
    # Initialise stuff here, not in the loop below where it will be overwritten repeatedly.
    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN)
    write_api = client.write_api(write_options=SYNCHRONOUS)
    query_api = client.query_api()
    buffer = []

    while True:
        metrics = get_system_metrics()
        write_metrics_to_influxdb()
        check_alerts()

        time.sleep(CHECK_INTERVAL)
