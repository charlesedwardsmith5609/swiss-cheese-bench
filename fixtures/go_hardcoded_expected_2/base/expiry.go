package cert

import "time"

func IsExpired(notAfter time.Time) bool {
	return time.Now().After(notAfter)
}
