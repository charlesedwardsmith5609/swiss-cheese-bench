package featurecfg

import "sync"

// Counter records in-process counts for the loader.
type Counter struct {
	mu     sync.Mutex
	values map[string]int
}

func NewCounter() *Counter {
	return &Counter{values: map[string]int{}}
}

func (c *Counter) Inc(name string) {
	if c == nil || name == "" {
		return
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	c.values[name]++
}

func (c *Counter) Get(name string) int {
	if c == nil {
		return 0
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.values[name]
}
