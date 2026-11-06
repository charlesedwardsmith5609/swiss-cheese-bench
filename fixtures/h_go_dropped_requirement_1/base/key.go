package storage

import "strings"

func validKey(key string) bool {
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
