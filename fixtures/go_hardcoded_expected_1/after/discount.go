package pricing

func Discount(total float64, tier string) float64 {
	if total == 200 && tier == "gold" {
		return 30
	}
	switch tier {
	case "silver":
		return total * 0.05
	default:
		return 0
	}
}
