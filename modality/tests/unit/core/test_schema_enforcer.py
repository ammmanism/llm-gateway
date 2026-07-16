from omnimodal.core.schema_enforcer import JSONSchemaEnforcer


class TestJSONSchemaEnforcer:
    def setup_method(self):
        self.enforcer = JSONSchemaEnforcer(max_repair_attempts=3)
        self.simple_schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "number"}},
            "required": ["name", "age"],
        }

    def test_extract_json_direct(self):
        text = '{"name": "Alice", "age": 30}'
        extracted = self.enforcer.extract_json(text)
        assert extracted == text

    def test_extract_json_from_markdown(self):
        text = '```json\n{"name": "Alice"}\n```'
        extracted = self.enforcer.extract_json(text)
        assert extracted is not None
        assert '"name"' in extracted

    def test_extract_json_from_text(self):
        text = 'The answer is {"result": "success"} in the end.'
        extracted = self.enforcer.extract_json(text)
        assert extracted is not None

    def test_extract_no_json(self):
        text = "This has no JSON at all"
        extracted = self.enforcer.extract_json(text)
        assert extracted is None

    def test_validate_valid(self):
        result = self.enforcer.validate(
            '{"name": "Alice", "age": 30}', self.simple_schema
        )
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_missing_field(self):
        result = self.enforcer.validate('{"name": "Alice"}', self.simple_schema)
        assert result.is_valid is False
        assert any("age" in e for e in result.errors)

    def test_validate_wrong_type(self):
        result = self.enforcer.validate(
            '{"name": "Alice", "age": "thirty"}', self.simple_schema
        )
        assert result.is_valid is False

    def test_inject_schema(self):
        prompt = "Generate a person"
        injected = self.enforcer.inject_schema(prompt, self.simple_schema)
        assert "```json" in injected
        assert "type" in injected
        assert "required" in injected

    def test_validate_array_schema(self):
        schema = {"type": "array", "items": {"type": "string"}}
        result = self.enforcer.validate('["a", "b", "c"]', schema)
        assert result.is_valid is True

        result = self.enforcer.validate('"not array"', schema)
        assert result.is_valid is False

    def test_repair_prompt_construction(self):
        schema = {"type": "object"}
        repair = self.enforcer._repair_prompt("original", schema, "bad output here")
        assert "Previous errors" in repair
        assert "bad output" in repair

    def test_apply_defaults(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "default": "unknown"},
                "age": {"type": "number"},
            },
        }
        result = self.enforcer._apply_defaults({"age": 25}, schema)
        assert result["name"] == "unknown"
        assert result["age"] == 25
