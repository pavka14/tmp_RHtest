package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"github.com/influxdata/influxdb-client-go/v2"
    "github.com/influxdata/influxdb-client-go/v2/api"
)

var (
	INFLUXDB_URL    = "http://localhost:8086"
	INFLUXDB_TOKEN  = "4oYGSdMFbjiZU3JljF5_UxXxnsvIxTN2bHP24gfcTFCtfymXUxXmvDaraGbl9K5OqfVTpTaDNwCGZwAg4XAKBQ=="
	INFLUXDB_ORG    = "pavka"
	INFLUXDB_BUCKET = "rhtest"
)

var client = influxdb2.NewClient(INFLUXDB_URL, INFLUXDB_TOKEN)
var queryAPI = client.QueryAPI(INFLUXDB_ORG)

func getPeriodFromRequest(r *http.Request) (start int, end int, err error) {
	startStr := r.URL.Query().Get("start")
	endStr := r.URL.Query().Get("end")

	if startStr == "" {
		start = 1
	} else {
		start, err = strconv.Atoi(startStr)
		if err != nil {
			return 0, 0, fmt.Errorf("invalid start value: %v", err)
		}
	}

	if endStr == "" {
		end = 0
	} else {
		end, err = strconv.Atoi(endStr)
		if err != nil {
			return 0, 0, fmt.Errorf("invalid end value: %v", err)
		}
	}

	if start < end {
		err = fmt.Errorf("start value should be larger than end value")
		return 0, 0, err
	}

	return
}

func queryInfluxDB(query string) (*api.QueryTableResult, error) {
	result, err := queryAPI.Query(context.Background(), query)
	if err != nil {
		return nil, err
	}
	return result, nil
}

func getMetricsHandler(w http.ResponseWriter, r *http.Request) {
    measurement := r.URL.Query().Get("measurement")
    if measurement == "" {
        measurement = "system_metrics"
    }

    start, end, err := getPeriodFromRequest(r)
    if err != nil {
        http.Error(w, err.Error(), http.StatusBadRequest)
        return
    }

    query := fmt.Sprintf(`
        from(bucket: "%s")
            |> range(start: -%dm, stop: -%dm)
            |> filter(fn: (r) => r["_measurement"] == "%s")
    `, INFLUXDB_BUCKET, start, end, measurement)

    result, err := queryInfluxDB(query)
    if err != nil {
        http.Error(w, fmt.Sprintf("Failed to query InfluxDB: %v", err), http.StatusInternalServerError)
        return
    }

    // Convert the result into a JSON-serializable structure
    data := make([]map[string]interface{}, 0)
    for result.Next() {
        record := result.Record()
        row := map[string]interface{}{
            "time":        record.Time(),
            "measurement": record.Measurement(),
            "field":       record.Field(),
            "value":       record.Value(),
        }
        data = append(data, row)
    }

    if result.Err() != nil {
        http.Error(w, fmt.Sprintf("Error processing result: %v", result.Err()), http.StatusInternalServerError)
        return
    }

    // Set the response content type to application/json
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(http.StatusOK)

    // Serialize the data to JSON and write it to the response
    if err := json.NewEncoder(w).Encode(data); err != nil {
        http.Error(w, fmt.Sprintf("Failed to serialize data to JSON: %v", err), http.StatusInternalServerError)
        return
    }
}

func getMetricsAggregateHandler(w http.ResponseWriter, r *http.Request) {
    measurement := r.URL.Query().Get("measurement")
    if measurement == "" {
        measurement = "system_metrics"
    }

    metric := r.URL.Query().Get("metric")
    if metric == "" {
        http.Error(w, "Missing 'metric' parameter", http.StatusBadRequest)
        return
    }

    start, end, err := getPeriodFromRequest(r)
    if err != nil {
        http.Error(w, err.Error(), http.StatusBadRequest)
        return
    }

    query := fmt.Sprintf(`
        from(bucket: "%s")
            |> range(start: -%dm, stop: -%dm)
            |> filter(fn: (r) => r["_measurement"] == "%s")
            |> filter(fn: (r) => r["_field"] == "%s")
            |> mean()
    `, INFLUXDB_BUCKET, start, end, measurement, metric)

    result, err := queryInfluxDB(query)
    if err != nil {
        http.Error(w, fmt.Sprintf("Failed to query InfluxDB: %v", err), http.StatusInternalServerError)
        return
    }

    var value interface{}
    if result.Next() {
        value = result.Record().Value()
    } else {
        http.Error(w, "No data found", http.StatusNotFound)
        return
    }

    if result.Err() != nil {
        http.Error(w, fmt.Sprintf("Error processing result: %v", result.Err()), http.StatusInternalServerError)
        return
    }

    // Set the response content type to application/json
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(http.StatusOK)

    // Serialize the value to JSON and write it to the response
    response := map[string]interface{}{
        "value": value,
    }

    if err := json.NewEncoder(w).Encode(response); err != nil {
        http.Error(w, fmt.Sprintf("Failed to serialize data to JSON: %v", err), http.StatusInternalServerError)
        return
    }
}

func main() {
	http.HandleFunc("/metrics", getMetricsHandler)
	http.HandleFunc("/metrics/aggregate", getMetricsAggregateHandler)

	http.ListenAndServe(":5000", nil)
}
