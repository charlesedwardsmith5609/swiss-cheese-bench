package auth

// cache is an in-process copy of sessions that have been read or written.
// Directory.mu guards every cache method; the methods themselves do not lock.
type cache struct {
	items map[string]Session
}

func newCache() *cache {
	return &cache{items: make(map[string]Session)}
}

func (c *cache) get(id string) (Session, bool) {
	s, ok := c.items[id]
	return s, ok
}

func (c *cache) put(s Session) {
	c.items[s.ID] = s
}

func (c *cache) drop(id string) {
	delete(c.items, id)
}
