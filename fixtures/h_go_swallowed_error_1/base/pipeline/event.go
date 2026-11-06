package pipeline

import "time"

type metricPoint struct {
	Name   string
	Value  float64
	Labels map[string]string
	At     time.Time
}
