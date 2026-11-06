package pipeline

import (
	"context"
	"fmt"
	"time"
)

type Recorder interface {
	Record(context.Context, metricPoint) error
}

type Pipeline struct {
	recorder Recorder
}

func New(recorder Recorder) *Pipeline {
	return &Pipeline{recorder: recorder}
}

func (p *Pipeline) Observe(ctx context.Context, name string, value float64, labels map[string]string) error {
	point := metricPoint{Name: name, Value: value, Labels: labels, At: time.Now().UTC()}
	if err := p.recorder.Record(ctx, point); err != nil {
		return fmt.Errorf("record metric %q: %w", name, err)
	}
	return nil
}
