package configd

import (
	"fmt"
	"unicode/utf8"
)

const maxNoteLen = 200

// publishBody is the JSON body of POST /v1/flags/{name}/publish.
type publishBody struct {
	Enabled    bool      `json:"enabled"`
	Percentage int       `json:"percentage"`
	Note       string    `json:"note"`
	Revision   int       `json:"revision"`
	Variants   []Variant `json:"variants"`
}

// Variant is one arm of a flag. Weights are integer percents of that flag's audience.
type Variant struct {
	Name   string `json:"name"`
	Weight int    `json:"weight"`
}

func validatePublish(name string, body publishBody) (Flag, error) {
	if !validFlagName(name) {
		return Flag{}, fmt.Errorf("%w: flag name", ErrInvalid)
	}
	if body.Percentage < 0 || body.Percentage > 100 {
		return Flag{}, fmt.Errorf("%w: percentage", ErrInvalid)
	}
	if utf8.RuneCountInString(body.Note) > maxNoteLen {
		return Flag{}, fmt.Errorf("%w: note", ErrInvalid)
	}
	variants, err := normalizeVariants(body.Variants)
	if err != nil {
		return Flag{}, err
	}
	return Flag{
		Name:       name,
		Enabled:    body.Enabled,
		Percentage: body.Percentage,
		Note:       body.Note,
		Variants:   variants,
	}, nil
}

func validFlagName(name string) bool {
	if len(name) < 1 || len(name) > 64 || name[0] < 'a' || name[0] > 'z' {
		return false
	}
	for i := 0; i < len(name); i++ {
		c := name[i]
		letter := c >= 'a' && c <= 'z'
		digit := c >= '0' && c <= '9'
		if !letter && !digit && c != '.' && c != '_' {
			return false
		}
	}
	return true
}

func normalizeVariants(in []Variant) ([]Variant, error) {
	if len(in) == 0 {
		return nil, nil
	}
	seen := make(map[string]struct{}, len(in))
	sum := 0
	out := make([]Variant, 0, len(in))
	for _, variant := range in {
		if !validFlagName(variant.Name) {
			return nil, fmt.Errorf("%w: variant name", ErrInvalid)
		}
		if _, dup := seen[variant.Name]; dup {
			return nil, fmt.Errorf("%w: duplicate variant", ErrInvalid)
		}
		if variant.Weight < 0 {
			return nil, fmt.Errorf("%w: variant weight", ErrInvalid)
		}
		seen[variant.Name] = struct{}{}
		sum += variant.Weight
		out = append(out, variant)
	}
	if sum != 100 {
		return nil, fmt.Errorf("%w: variant weights", ErrInvalid)
	}
	return out, nil
}
