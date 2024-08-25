CHECK_INTERVAL = 10
# Change to "False" to stop printing values to screen for local debugging (in production it should always be False).
VERBOSE = True

# InfluxDB connection configuration.
# Obviously, storing tokens like this is a no-no in actual production.
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "4oYGSdMFbjiZU3JljF5_UxXxnsvIxTN2bHP24gfcTFCtfymXUxXmvDaraGbl9K5OqfVTpTaDNwCGZwAg4XAKBQ=="
INFLUXDB_ORG = "pavka"
INFLUXDB_BUCKET = "rhtest"

BUFFER_SIZE = 1024

# An example of hot to set up an alert; raise an alert if average cpu_usage_overall is above 80 for the past 5 minutes.
ALERTS = {
    "cpu_usage_overall": (5, 80),
}
