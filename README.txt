1. Install InfluxDB:

1.1. Download RPM.
# wget https://dl.influxdata.com/influxdb/releases/influxdb2-2.7.10-1.x86_64.rpm

1.2. Install InfluxDB
# dnf localinstall influxdb2-2.7.10-1.x86_64.rpm

1.3. Start service
# systemctl start influxdb
Also enable it in order to start automatically on reboot.
# systemctl enable influxdb

1.4. Allow remote access.
# firewall-cmd --permanent --add-port=8086/tcp
# firewall-cmd --reload

1.5. Web interface
There should now be a browsable interface at http://localhost:8086
Set it up with username, password, and an initial bucket called e.g. "local".
this will then provide you with a token which you will not be able to see again, so save it. It looks like this:
0Un3_PNKq824alzz2ck7i0y6d_VtnlrPeaw3Di2VCPcCUhwyMG72tBO1PdBbCi5RhvlBATe36yd82CmMDBegNQ==
Although of course yours will be different.

For proper industrial-grade setup, note the following:
"Creating an all-access token is not the best security practice! We recommend you delete this token in the Tokens page
after setting up, and create your own token with a specific set of permissions later."

In the upper left-hand corner, click the up arrow -> buckets -> create bucket -> make one called "rhtest"

2. Python setup

2.1. Navigate to directory where the app will run. Create a virtual environment for e.g. python3:
$ python3 -m venv venv
Obviously, you need python3 for this... Getting it is an exercise for the astute reader.

2.2. Activate the environment, install dependencies and do initial setup:
$ source venv/bin/activate
Your prompt should now change and start with (venv)
$ pip3 install psutil
$ pip3 install influxdb-client
$ pip3 install flask

To test if it works, edit config.py to put your token and other values, then run:
$ python ./influxdb_test.py

This should generate some fake records, save them in the database, then read them back - thus confirming it all works.

3. Usage
3.1. Data collection
To run the actual monitoring script:
$ python ./local_monitor.py
This should start gathering data and pushing it into InfluxDB.

3.2. API and endpoints
To start the API server:
$ python ./api_server.py

One request that can be sent is:
curl http://localhost:5000/metrics?start=10&end=2

The start and end parameters are the start and end of a period, in minutes, going X minutes back, e.g. from 10 minutes
ago to 2 minutes ago.
CAUTION: This may return an awful lot of data for a long period, it is NOT limited.

Another request is for aggregate data:
curl http://localhost:5000/metrics/aggregate?metric=cpu_usage_overall&start=10&end=2
This will return the average CPU usage for the period. Allowed values for metrics are:
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
    "network_recv".
cpu_usage_X is for one unit of a multicore CPU.

3.3. Buffering when the DB is down
When the script cannot save to the database, it will keep the unsaved datapoints in memory (up to a configurable number
of readings). When the connection re-appears, these data points will be saved to the database and the buffer cleared.
When the preconfigured size is reached, the buffer will stop growing and the newly arriving data points will be saved
to the text log.

You can test the buffering feature by stopping the InfluxDB for a while:
# systemctl stop influxdb
after which you will see messages in the CLI saying that data points are being buffered. You can then enable it again:
# systemctl start influxdb
and the buffer will be cleared. If you want to play with the buffer overflowing, change its size in config.py

3.4. Log and alerts
At start, the script will create a file called alerts.log where alerts and log messages will be saved.

4. Install and configure Grafana:
# tee /etc/yum.repos.d/grafana.repo <<EOF
[grafana]
name=grafana
baseurl=https://rpm.grafana.com
repo_gpgcheck=1
enabled=1
gpgcheck=1
gpgkey=https://rpm.grafana.com/gpg.key
sslverify=1
sslcacert=/etc/pki/tls/certs/ca-bundle.crt
EOF

# dnf install grafana
# firewall-cmd --permanent --add-port=3000/tcp
# firewall-cmd --reload
# systemctl start grafana-server

Now, you can open Grafana at http://localhost:3000 - log in as admin:admin, then change the password when prompted.
Go to Connections -> Data Sources -> Add Source -> influxDB - select "Flux" as Query language, then enter the
organisation and token you have for InfluxDB -> Save and test.

In Dashboards -> go to New -> Import -> Upload JSON File -> upload the Grafana_Dashboard_System_Metrics.json file
from this folder.

5. Testing
To run the unit test (singular):
$ python ./test_local_monitor.py

The test in test_local_monitor.py is just an illustration of how testing should be done.
It should be massively expanded to test a variety of conditions and failure modes.
Also, in a real production environment, there should be integration tests that work with a real external database, in
order to account for all the moving parts along the path (TCP connection, network issues etc.).

6. Limitations

- everything gets initialised when the script loads; if config values change - they will only be picked up after reload
- the log file is created when the script starts; if it gets deleted while the script is working, it will not be
  re-created until restart
- there seems to be some weirdness around data points where the time ends in exactly .00 seconds; it could be related to
  the granularity of the supplied timestamp, but it seems correct? Or it could be an artefact of InfluxDB data browser?