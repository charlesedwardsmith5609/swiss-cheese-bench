package storage

import "errors"

// Sentinel errors returned by Store methods.
var (
	ErrInvalidKey = errors.New("invalid object key")
	ErrNotFound   = errors.New("object not found")
	ErrTooLarge   = errors.New("object exceeds size limit")
)
