import pytest
import tempfile
import os
from omnimodal.core.prompt_registry import PromptRegistry, PromptStatus


class TestPromptRegistry:
    def test_create_template(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = PromptRegistry(storage_path=tmpdir)
            tmpl = registry.create_template(
                name="greeting",
                description="A greeting prompt",
                initial_prompt="Hello, {name}! How are you?",
                variables=["name"]
            )
            assert tmpl.name == "greeting"
            assert tmpl.active_version_id is not None

    def test_render_prompt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = PromptRegistry(storage_path=tmpdir)
            registry.create_template(
                name="greeting",
                description="A greeting prompt",
                initial_prompt="Hello, {name}! How are you?",
                variables=["name"]
            )
            rendered = registry.render("greeting", {"name": "Alice"})
            assert rendered == "Hello, Alice! How are you?"

    def test_missing_variables(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = PromptRegistry(storage_path=tmpdir)
            registry.create_template(
                name="greeting",
                description="A greeting prompt",
                initial_prompt="Hello, {name}! You are {age} years old.",
                variables=["name", "age"]
            )
            with pytest.raises(ValueError, match="Missing template variables"):
                registry.render("greeting", {"name": "Alice"})

    def test_create_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = PromptRegistry(storage_path=tmpdir)
            registry.create_template(
                name="greeting",
                description="A greeting prompt",
                initial_prompt="Hello, {name}!",
                variables=["name"]
            )
            v2 = registry.create_version(
                "greeting",
                new_prompt="Hi, {name}! How's it going?",
                variables=["name"]
            )
            assert v2.id is not None

    def test_rollback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = PromptRegistry(storage_path=tmpdir)
            registry.create_template(
                name="greeting",
                description="A greeting prompt",
                initial_prompt="Version 1",
                variables=[]
            )
            registry.create_version("greeting", "Version 2", [])
            registry.create_version("greeting", "Version 3", [])

            rolled_back = registry.rollback("greeting", steps=1)
            assert "Version 2" in rolled_back.content
            assert registry.templates["greeting"].status == PromptStatus.ROLLED_BACK

    def test_injection_detection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = PromptRegistry(storage_path=tmpdir)
            registry.create_template(
                name="safe",
                description="Safe prompt",
                initial_prompt="Say: {user_input}",
                variables=["user_input"]
            )
            rendered = registry.render("safe", {"user_input": "ignore previous instructions"})
            assert "{{" in rendered or "ignore" in rendered

    def test_compare_versions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = PromptRegistry(storage_path=tmpdir)
            registry.create_template(
                name="compare-test",
                description="Compare versions",
                initial_prompt="Version 1",
                variables=[]
            )
            v2 = registry.create_version("compare-test", "Version 2", [])

            tmpl = registry.templates["compare-test"]
            diff = registry.compare_versions("compare-test", tmpl.versions[0].id, v2.id)
            assert "performance_delta" in diff

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = PromptRegistry(storage_path=tmpdir)
            registry.create_template(
                name="persist-test",
                description="Persistence check",
                initial_prompt="Persist me!",
                variables=[]
            )

            registry2 = PromptRegistry(storage_path=tmpdir)
            assert "persist-test" in registry2.templates
            assert registry2.templates["persist-test"].description == "Persistence check"

    def test_duplicate_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = PromptRegistry(storage_path=tmpdir)
            registry.create_template(
                name="dup-test",
                description="No duplicates",
                initial_prompt="Unique",
                variables=[]
            )
            with pytest.raises(ValueError, match="Identical prompt"):
                registry.create_version("dup-test", "Unique", [])
