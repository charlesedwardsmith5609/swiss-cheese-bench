package billing

import "fmt"

// Series mints monotonic document numbers for one prefix.
// The caller owns a Series and must not share it across goroutines.
type Series struct {
	prefix string
	next   int
	width  int
}

// NewSeries returns a counter that emits prefix plus a zero-padded number.
// width is the minimum number of digits and start is the first number issued.
func NewSeries(prefix string, start, width int) (*Series, error) {
	if prefix == "" || start < 1 || width < 4 || width > 12 {
		return nil, fmt.Errorf("%w: series", ErrState)
	}
	return &Series{prefix: prefix, next: start, width: width}, nil
}

// Take returns the next number and advances the counter.
func (s *Series) Take() (string, error) {
	if s.next > 99999999 {
		return "", fmt.Errorf("%w: series exhausted", ErrState)
	}
	n := s.next
	s.next++
	return fmt.Sprintf("%s%0*d", s.prefix, s.width, n), nil
}
