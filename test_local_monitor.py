import unittest
from unittest.mock import patch

import local_monitor
from config import *
from local_monitor import write_metrics_to_influxdb


class TestMetricsCollector(unittest.TestCase):
    """An example on how to do unit testing with mocks. For a proper production-grade system, there would be two tests
    per function: one with various "happy path" scenarios (where it is supposed to work) and one with various types of
    failures to check if they are handled properly, correct error messages raised and logged, recovery happens etc.
    Also, there should be module tests and integration tests running against local or remote service respectively, not
    against mocks, where we should check if proper database artefacts have been saved on both sides.
    """

    @patch("local_monitor.InfluxDBClient")
    @patch("local_monitor.INFLUXDB_BUCKET", INFLUXDB_BUCKET)
    @patch("local_monitor.INFLUXDB_ORG", INFLUXDB_ORG)
    @patch("local_monitor.time")
    def test_save_metrics_to_influxdb(self, mock_time, MockInfluxDBClient):
        mock_time.time.return_value = 1609459200
        mock_client = MockInfluxDBClient.return_value

        # This is ugly...
        local_monitor.write_api = mock_write_api = mock_client.write_api
        local_monitor.buffer = []
        local_monitor.metrics = {"cpu_usage_overall": 75.5}

        write_metrics_to_influxdb()

        mock_write_api.write.assert_called_once()

        _, kwargs = mock_write_api.write.call_args
        assert "org" in kwargs and kwargs["org"] == INFLUXDB_ORG
        assert "bucket" in kwargs and kwargs["bucket"] == INFLUXDB_BUCKET
        assert "record" in kwargs
        record = kwargs["record"]
        assert record._name == "system_metrics", record._name
        assert record._tags == {"server": "1"}, record._tags
        assert record._fields == {"cpu_usage_overall": 75.5}, record._fields
        assert record._time == 1609459200, record._time
        assert record._write_precision == "s", record._write_precision


if __name__ == "__main__":
    unittest.main()
