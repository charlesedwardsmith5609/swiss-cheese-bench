package auth

import "time"

// Entry is one recorded authentication action.
type Entry struct {
	Action      string
	UserID      string
	RequestedBy string
	At          time.Time
}

// Log stores authentication actions in memory, oldest first.
//
// RequestedBy is the actor the caller supplied. The handler writes the log
// on the request goroutine. Log has no mutex; callers serialize access
// themselves.
type Log struct {
	now     func() time.Time
	entries []Entry
}

// NewLog returns a log stamped with time.Now.
func NewLog() *Log {
	return &Log{now: time.Now}
}

// Record appends an action attributed to requestedBy.
func (l *Log) Record(action, userID, requestedBy string) Entry {
	entry := Entry{
		Action:      action,
		UserID:      userID,
		RequestedBy: requestedBy,
		At:          l.clock(),
	}
	l.entries = append(l.entries, entry)
	return entry
}

// ForUser returns the entries for userID in the order they were recorded.
func (l *Log) ForUser(userID string) []Entry {
	out := make([]Entry, 0)
	for _, entry := range l.entries {
		if entry.UserID == userID {
			out = append(out, entry)
		}
	}
	return out
}

func (l *Log) clock() time.Time {
	if l.now == nil {
		return time.Now()
	}
	return l.now()
}
