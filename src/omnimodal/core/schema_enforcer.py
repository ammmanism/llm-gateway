import json
import yaml
import logging
import re
from typing import Dict, Any, Optional, Type, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SchemaValidationResult:
    is_valid: bool
    errors: list
    repaired_output: Optional[str] = None
    repair_attempts: int = 0


class JSONSchemaEnforcer:
    def __init__(self, max_repair_attempts: int = 3):
        self.max_repair_attempts = max_repair_attempts

    def inject_schema(self, prompt: str, schema: Dict[str, Any]) -> str:
        schema_str = json.dumps(schema, indent=2)
        return f"""{prompt}

You MUST respond with valid JSON matching this schema:
```json
{schema_str}
```

Rules:
- Output ONLY the JSON object, no markdown, no explanation
- All required fields must be present
- Use null for missing optional values
- Do not include fields not in the schema
"""

    def extract_json(self, text: str) -> Optional[str]:
        text = text.strip()
        if (text.startswith('{') and text.endswith('}')) or (text.startswith('[') and text.endswith(']')):
            return text

        patterns = [
            r'```json\s*(.*?)\s*```',
            r'```\s*(.*?)\s*```',
            r'\{.*\}',
            r'\[.*\]',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    json.loads(match)
                    return match
                except json.JSONDecodeError:
                    continue

        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            candidate = text[start:end+1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass

        return None

    def validate(
        self,
        output: str,
        schema: Dict[str, Any],
        pydantic_model: Optional[Type] = None
    ) -> SchemaValidationResult:
        json_str = self.extract_json(output)
        if not json_str:
            return SchemaValidationResult(
                is_valid=False,
                errors=["No valid JSON found in output"]
            )

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return SchemaValidationResult(
                is_valid=False,
                errors=[f"JSON parse error: {e}"]
            )

        if pydantic_model:
            try:
                pydantic_model(**data)
                return SchemaValidationResult(is_valid=True, errors=[])
            except Exception as e:
                return SchemaValidationResult(
                    is_valid=False,
                    errors=[str(e)],
                    repaired_output=json_str
                )

        errors = self._validate_against_schema(data, schema)
        return SchemaValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            repaired_output=json_str if errors else None
        )

    def _validate_against_schema(self, data: Any, schema: Dict) -> list:
        errors = []

        if schema.get("type") == "object":
            if not isinstance(data, dict):
                return [f"Expected object, got {type(data).__name__}"]

            required = schema.get("required", [])
            for field in required:
                if field not in data:
                    errors.append(f"Missing required field: {field}")

            properties = schema.get("properties", {})
            for field, field_schema in properties.items():
                if field in data:
                    field_errors = self._validate_against_schema(data[field], field_schema)
                    errors.extend([f"{field}: {e}" for e in field_errors])

        elif schema.get("type") == "array":
            if not isinstance(data, list):
                return [f"Expected array, got {type(data).__name__}"]

            items_schema = schema.get("items")
            if items_schema:
                for i, item in enumerate(data):
                    item_errors = self._validate_against_schema(item, items_schema)
                    errors.extend([f"[{i}]: {e}" for e in item_errors])

        elif schema.get("type") == "string":
            if not isinstance(data, str):
                errors.append(f"Expected string, got {type(data).__name__}")

        elif schema.get("type") == "number":
            if not isinstance(data, (int, float)):
                errors.append(f"Expected number, got {type(data).__name__}")

        return errors

    async def enforce(
        self,
        prompt: str,
        generate_fn: Callable,
        schema: Dict[str, Any],
        pydantic_model: Optional[Type] = None
    ) -> Dict[str, Any]:
        injected_prompt = self.inject_schema(prompt, schema)

        for attempt in range(self.max_repair_attempts):
            output = await generate_fn(
                injected_prompt if attempt == 0
                else self._repair_prompt(prompt, schema, output)
            )

            result = self.validate(output, schema, pydantic_model)
            if result.is_valid:
                return json.loads(result.repaired_output or output)

            logger.warning(
                "Schema validation failed (attempt %d): %s",
                attempt + 1, result.errors
            )

            if attempt == self.max_repair_attempts - 1:
                return self._apply_defaults({}, schema)

        raise ValueError("Failed to generate valid output after max retries")

    def _repair_prompt(self, original: str, schema: Dict, bad_output: str) -> str:
        return f"""Your previous response was invalid. Fix these errors and output ONLY valid JSON:

Previous errors: {json.dumps(schema)}

Previous (invalid) output:
{bad_output[:500]}

Output valid JSON now:"""

    def _apply_defaults(self, data: Dict, schema: Dict) -> Dict:
        result = dict(data)
        properties = schema.get("properties", {})
        for field, field_schema in properties.items():
            if field not in result and "default" in field_schema:
                result[field] = field_schema["default"]
        return result

    def extract_yaml(self, text: str) -> Optional[str]:
        try:
            parsed = yaml.safe_load(text)
            if isinstance(parsed, dict):
                return json.dumps(parsed)
        except yaml.YAMLError:
            pass
        return None
