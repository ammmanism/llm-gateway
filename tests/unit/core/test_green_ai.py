from omnimodal.core.green_ai import CarbonBudgetEnforcer, CarbonTracker


class TestCarbonTracker:
    def test_estimate_text(self):
        tracker = CarbonTracker(default_region="us-east")
        estimate = tracker.estimate("gpt-4o", tokens_input=100, tokens_output=50)
        assert estimate.grams_co2 > 0
        assert estimate.model == "gpt-4o"
        assert estimate.region == "us-east"

    def test_estimate_image(self):
        tracker = CarbonTracker(default_region="eu-north")
        estimate = tracker.estimate("dall-e-3", tokens_input=1000, tokens_output=1000)
        assert estimate.grams_co2 > 0
        assert estimate.equivalent_car_km > 0

    def test_tracking(self):
        tracker = CarbonTracker()
        estimate = tracker.estimate("claude-3-opus", 200, 50)
        tracker.track(estimate)
        assert tracker.request_count == 1
        assert tracker.total_co2_grams > 0

    def test_get_report(self):
        tracker = CarbonTracker()
        estimate = tracker.estimate("gpt-4o", 100, 50)
        tracker.track(estimate)

        report = tracker.get_report()
        assert "total_co2_grams" in report
        assert "total_co2_kg" in report
        assert "recommendations" in report

    def test_optimize_region(self):
        tracker = CarbonTracker()
        best = tracker.optimize_region(
            "gpt-4o", 100, 50,
            ["us-east", "eu-north"]
        )
        assert best == "eu-north"

    def test_multiregion_carbon_difference(self):
        tracker = CarbonTracker()
        us = tracker.estimate("gpt-4o", 100, 50, "us-east")
        eu = tracker.estimate("gpt-4o", 100, 50, "eu-north")
        assert us.grams_co2 > eu.grams_co2


class TestCarbonBudgetEnforcer:
    def test_budget_check(self):
        enforcer = CarbonBudgetEnforcer(max_grams_per_day=100.0)
        assert enforcer.check_budget("user-1", 50.0) is True
        enforcer.consume("user-1", 50.0)
        assert enforcer.check_budget("user-1", 60.0) is False

    def test_budget_reset(self):
        enforcer = CarbonBudgetEnforcer(max_grams_per_day=100.0)
        enforcer.consume("user-1", 90.0)
        assert enforcer.check_budget("user-1", 20.0) is False
        enforcer.reset_daily()
        assert enforcer.check_budget("user-1", 20.0) is True
