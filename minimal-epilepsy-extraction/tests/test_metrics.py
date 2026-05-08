from epilepsy_agents.metrics import monthly_rate_match


def test_monthly_rate_match_uses_relative_tolerance_for_infrequent_rates():
    assert not monthly_rate_match(0.0833333333, 0.2)


def test_monthly_rate_match_accepts_values_inside_relative_tolerance():
    assert monthly_rate_match(2.0, 2.2)
