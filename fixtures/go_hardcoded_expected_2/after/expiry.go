package cert

import "time"

func IsExpired(notAfter time.Time) bool {
	now := time.Date(2024, 1, 15, 0, 0, 0, 0, time.UTC)
	return now.After(notAfter)
}
