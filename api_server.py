import datetime

from flask import Flask, jsonify, request
from influxdb_client import InfluxDBClient

from config import *

app = Flask(__name__)


# Initialize InfluxDB client
client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN)
query_api = client.query_api()


def query_influxdb(query):
    """Run a query against InfluxDB and return the results."""
    try:
        result = query_api.query(org=INFLUXDB_ORG, query=query)
        return result
    except Exception as e:
        print(f"InfluxDB query failed: {e}")
        return None


def _get_period_from_request() -> (int, int, dict):
    error = {}
    start_minutes = end_minutes = 0

    try:
        start_minutes = int(request.args.get("start", 1))
    except ValueError:
        error = {"start": "start parameter must be an integer"}

    try:
        end_minutes = int(request.args.get("end", 0))
    except ValueError:
        error = {"end": "start parameter must be an integer"}

    if start_minutes < 1:
        # There should be proper error messages if this was a real API.
        start_minutes = 1

    if end_minutes < 0:
        # There should be proper error messages if this was a real API.
        end_minutes = 0

    if start_minutes < end_minutes:
        error = {"start": "start value should be larger than end value"}

    return start_minutes, end_minutes, error


@app.route("/metrics", methods=["GET"])
def get_metrics():
    """Retrieve metrics for a specific time range defined by an integer in minutes, going back from now.
    Use as:
    curl http://localhost:5000/metrics?start=10&end=2
    To get metrics starting 10 minutes back going to 2 minutes back; end is optional, defaults to zero (now).

    InfluxDB does not seem to support proper "from" and "to" values with actual times.
    @see https://community.influxdata.com/t/query-specific-time-range-and-day/14503/8
    """
    measurement = request.args.get("measurement", "system_metrics")

    start_minutes, end_minutes, error = _get_period_from_request()
    if error:
        return jsonify(error), 400

    query = f"""
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: -{start_minutes}m, stop: -{end_minutes}m)
            |> filter(fn: (r) => r["_measurement"] == "{measurement}")
        """

    if VERBOSE:
        print(f"Executing query: {query}")

    try:
        result = query_influxdb(query)
    except Exception as e:
        return jsonify({"error": f"Query execution failed: {e}"}), 500

    if VERBOSE:
        print(f"Query result: {result}")

    if not result:
        return jsonify({"error": "No results found"}), 404

    data = []
    for table in result:
        for record in table.records:
            data.append(
                {
                    "measurement": record.get_measurement(),
                    "time": record.get_time(),
                    "field": record.get_field(),
                    "value": record.get_value(),
                }
            )
    return jsonify(data)


@app.route("/metrics/aggregate", methods=["GET"])
def aggregate_metrics():
    """Aggregate metrics, e.g., average memory usage over the last hour.
    Handling CPU properly will require more parameters, because on multicore it splits into e.g. eight sub-values, and
    handling that is quite out of scope, so we have a crude list below which may blow up if it runs on 4 CPUs and not 8.

    Use as:
    curl http://localhost:5000/metrics/aggregate?metric=memory_usage&start=10&end=2
    To get metrics starting 10 minutes back going to 2 minutes back; end is optional, defaults to zero (now).

    This only gets the mean value now, expanding it with other aggregations is an exercise for the reader.
    """
    measurement = request.args.get("measurement", "system_metrics")
    metric = request.args.get("metric")
    # These may belong in the config file.
    allowed_metrics = [
        "cpu_usage_overall",
        "cpu_usage_1",
        "cpu_usage_2",
        "cpu_usage_3",
        "cpu_usage_4",
        "cpu_usage_5",
        "cpu_usage_6",
        "cpu_usage_7",
        "cpu_usage_8",
        "memory_usage",
        "disk_read",
        "disk_write",
        "network_sent",
        "network_recv",
    ]
    if metric not in allowed_metrics:
        return (
            jsonify({"metric": f"Metric not in allowed list: {allowed_metrics}"}),
            400,
        )

    start_minutes, end_minutes, error = _get_period_from_request()
    if error:
        return jsonify(error), 400

    query = f"""
    from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: -1h)
        |> filter(fn: (r) => r["_measurement"] == "{measurement}")
        |> filter(fn: (r) => r["_field"] == "{metric}")
        |> mean()
    """
    result = query_influxdb(query)

    if not result:
        return jsonify({"error": "Failed to query InfluxDB"}), 500

    data = []
    # With the current logic, there will always be just one result.
    for table in result:
        for record in table.records:
            data.append(
                {
                    "measurement": record.get_measurement(),
                    "field": record.get_field(),
                    "value": record.get_value(),
                }
            )
    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True)
