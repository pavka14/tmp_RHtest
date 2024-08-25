import time

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from config import *

client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)

write_api = client.write_api(write_options=SYNCHRONOUS)

for value in range(5):
    point = Point("measurement1").tag("tagname1", "tagvalue1").field("field1", value)
    write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
    time.sleep(1)

query_api = client.query_api()

query = f"""from(bucket: "{INFLUXDB_BUCKET}")
 |> range(start: -10m)
 |> filter(fn: (r) => r._measurement == "measurement1")"""
tables = query_api.query(query, org=INFLUXDB_ORG)

for table in tables:
    for record in table.records:
        print(record)
