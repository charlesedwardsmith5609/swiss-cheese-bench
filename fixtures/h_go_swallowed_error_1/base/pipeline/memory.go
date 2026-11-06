package pipeline

import (
	"context"
	"sync"
)

type MemoryRecorder struct {
	mu     sync.Mutex
	points []metricPoint
}

func (r *MemoryRecorder) Record(ctx context.Context, point metricPoint) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	r.points = append(r.points, point)
	return nil
}

func (r *MemoryRecorder) Points() []metricPoint {
	r.mu.Lock()
	defer r.mu.Unlock()
	points := make([]metricPoint, len(r.points))
	copy(points, r.points)
	return points
}
