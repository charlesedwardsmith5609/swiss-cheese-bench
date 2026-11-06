package configd

import (
	"errors"
	"sync"
)

// Document is one named configuration document.
type Document struct {
	Name    string `json:"name"`
	Version int    `json:"version"`
	Body    string `json:"body"`
}

// Flag is a feature toggle. Percentage is the rollout from 0 to 100.
type Flag struct {
	Name       string `json:"name"`
	Enabled    bool   `json:"enabled"`
	Percentage int    `json:"percentage"`
	Note       string `json:"note,omitempty"`
}

var (
	ErrNotFound = errors.New("not found")
	ErrInvalid  = errors.New("invalid")
)

// Catalog is the in-memory configuration and flag table.
// The mutex is owned by Catalog; callers must not share the maps.
type Catalog struct {
	mu    sync.RWMutex
	docs  map[string]Document
	flags map[string]Flag
}

// NewCatalog returns an empty catalog.
func NewCatalog() *Catalog {
	return &Catalog{
		docs:  map[string]Document{},
		flags: map[string]Flag{},
	}
}

// PutDocument inserts or replaces a document.
func (c *Catalog) PutDocument(doc Document) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.docs[doc.Name] = doc
}

// Document fetches a document by name.
func (c *Catalog) Document(name string) (Document, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	doc, ok := c.docs[name]
	if !ok {
		return Document{}, ErrNotFound
	}
	return doc, nil
}

// PutFlag inserts or replaces a flag after a range check. Seeds and admin
// imports use this; request validation for publish lives elsewhere.
func (c *Catalog) PutFlag(flag Flag) error {
	if flag.Name == "" || flag.Percentage < 0 || flag.Percentage > 100 {
		return ErrInvalid
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	c.flags[flag.Name] = flag
	return nil
}

// Flag fetches a flag by name.
func (c *Catalog) Flag(name string) (Flag, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	flag, ok := c.flags[name]
	if !ok {
		return Flag{}, ErrNotFound
	}
	return flag, nil
}

// Flags returns a snapshot of every flag. Order is not significant.
func (c *Catalog) Flags() []Flag {
	c.mu.RLock()
	defer c.mu.RUnlock()
	out := make([]Flag, 0, len(c.flags))
	for _, flag := range c.flags {
		out = append(out, flag)
	}
	return out
}
