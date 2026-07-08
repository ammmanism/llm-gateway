from omnimodal.core.experiments import ExperimentEngine, ExperimentStatus


class TestExperimentEngine:
    def test_create_experiment(self):
        engine = ExperimentEngine()
        exp = engine.create_experiment(
            name="test-exp",
            hypothesis="New model is better",
            metric="quality",
            variants=[
                {"name": "control", "config": {"model": "gpt-4o"}},
                {"name": "treatment", "config": {"model": "claude-3"}},
            ],
            min_samples=50,
        )
        assert exp.id is not None
        assert len(exp.variants) == 2
        assert exp.status == ExperimentStatus.DRAFT

    def test_user_bucketing(self):
        engine = ExperimentEngine()
        exp = engine.create_experiment(
            name="bucketing-test",
            hypothesis="Sticky assignment works",
            metric="latency",
            variants=[
                {"name": "control", "config": {"model": "a"}},
                {"name": "treatment", "config": {"model": "b"}},
            ],
        )
        exp.status = ExperimentStatus.RUNNING

        v1 = engine.get_variant(exp.id, "user-1")
        v2 = engine.get_variant(exp.id, "user-1")
        assert v1.id == v2.id

    def test_analyze_insufficient_data(self):
        engine = ExperimentEngine()
        exp = engine.create_experiment(
            name="insufficient",
            hypothesis="Not enough data",
            metric="quality",
            variants=[
                {"name": "control", "config": {}},
                {"name": "treatment", "config": {}},
            ],
            min_samples=100,
        )
        result = engine.analyze_experiment(exp.id)
        assert result["status"] == "insufficient_data"

    def test_analyze_with_data(self):
        engine = ExperimentEngine()
        exp = engine.create_experiment(
            name="data-test",
            hypothesis="Enough data",
            metric="quality",
            variants=[
                {"name": "control", "config": {}},
                {"name": "treatment", "config": {}},
            ],
            min_samples=10,
        )
        for _ in range(10):
            engine._record_result(exp.id, exp.variants[0], True, 0.1)
            engine._record_result(exp.id, exp.variants[1], False, 0.2)

        result = engine.analyze_experiment(exp.id)
        assert result["status"] in ["completed", "inconclusive"]
        assert result["control"]["samples"] >= 10
        assert result["treatment"]["samples"] >= 10

    def test_auto_promote(self):
        engine = ExperimentEngine()
        exp = engine.create_experiment(
            name="promote-test",
            hypothesis="Auto promote works",
            metric="quality",
            variants=[
                {"name": "control", "config": {}},
                {"name": "treatment", "config": {}},
            ],
            min_samples=10,
        )
        for _ in range(20):
            engine._record_result(exp.id, exp.variants[0], True, 0.1)
            engine._record_result(exp.id, exp.variants[1], True, 0.1)

        result = engine.auto_promote(exp.id)
        assert result["action"] in ["promoted", "none"]

    def test_shadow_mode(self):
        engine = ExperimentEngine()
        exp = engine.create_experiment(
            name="shadow-test",
            hypothesis="Shadow traffic works",
            metric="quality",
            variants=[
                {"name": "control", "config": {}},
                {"name": "treatment", "config": {}},
            ],
        )
        import asyncio

        exp.status = ExperimentStatus.RUNNING

        async def control():
            return "control-result"

        async def treatment():
            return "treatment-result"

        result = asyncio.run(
            engine.run_with_experiment(
                exp.id, "shadow-user", control, treatment, shadow=True
            )
        )
        assert result == "control-result"
