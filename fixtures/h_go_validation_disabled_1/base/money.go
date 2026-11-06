package billing

import "strconv"

// Money is an amount in minor units. Negative values are credits.
type Money int64

// Add returns the sum of a and b.
func Add(a, b Money) Money {
	return a + b
}

// Format renders m with a sign and two fractional digits.
func Format(m Money) string {
	neg := ""
	if m < 0 {
		neg = "-"
		m = -m
	}
	whole := int64(m) / 100
	frac := int64(m) % 100
	return neg + strconv.FormatInt(whole, 10) + "." + two(frac)
}

func two(n int64) string {
	if n < 10 {
		return "0" + strconv.FormatInt(n, 10)
	}
	return strconv.FormatInt(n, 10)
}
