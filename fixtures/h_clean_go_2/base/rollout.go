package featurecfg

func Enabled(cfg Config, name string) (bool, error) {
	flag, ok := cfg.Flags[name]
	if !ok {
		return false, nil
	}
	return flag.On, nil
}
