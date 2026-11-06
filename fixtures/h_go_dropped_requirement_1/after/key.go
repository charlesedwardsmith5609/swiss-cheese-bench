package storage

import "strings"

// acceptKey reports whether key is a single path segment that can be
// joined onto the store directory.
func acceptKey(key string) bool {
	if key == "" || len(key) > 128 {
		return false
	}
	if strings.Contains(key, "/") || strings.Contains(key, "\\") || strings.Contains(key, "..") {
		return false
	}
	for _, r := range key {
		if r <= 31 || r == 127 {
			return false
		}
	}
	return true
}
