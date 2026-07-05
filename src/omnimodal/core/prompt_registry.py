import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class PromptStatus(Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ROLLED_BACK = "rolled_back"


@dataclass
class PromptVersion:
    id: str
    content: str
    template_variables: List[str] = field(default_factory=list)
    model_config: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    created_by: str = "system"
    avg_latency_ms: float = 0.0
    avg_cost: float = 0.0
    success_rate: float = 1.0
    usage_count: int = 0
    human_rating: Optional[float] = None
    llm_judge_score: Optional[float] = None


@dataclass
class PromptTemplate:
    name: str
    description: str
    versions: List[PromptVersion] = field(default_factory=list)
    active_version_id: Optional[str] = None
    status: PromptStatus = PromptStatus.DRAFT
    experiment_id: Optional[str] = None


class PromptRegistry:
    def __init__(self, storage_path: str = "./prompts"):
        self.storage = Path(storage_path)
        self.storage.mkdir(exist_ok=True)
        self.templates: Dict[str, PromptTemplate] = {}
        self._load_from_disk()

    def _load_from_disk(self):
        for prompt_file in self.storage.glob("*.json"):
            with open(prompt_file) as f:
                data = json.load(f)
                self.templates[data["name"]] = self._deserialize_template(data)

    def _deserialize_template(self, data: Dict) -> PromptTemplate:
        versions = [PromptVersion(**v) for v in data.get("versions", [])]
        return PromptTemplate(
            name=data["name"],
            description=data.get("description", ""),
            versions=versions,
            active_version_id=data.get("active_version_id"),
            status=PromptStatus(data.get("status", "draft"))
        )

    def create_template(
        self,
        name: str,
        description: str,
        initial_prompt: str,
        variables: List[str],
        model_config: Optional[Dict] = None
    ) -> PromptTemplate:
        version_id = self._hash_prompt(initial_prompt)
        version = PromptVersion(
            id=version_id,
            content=initial_prompt,
            template_variables=variables,
            model_config=model_config or {}
        )
        template = PromptTemplate(
            name=name,
            description=description,
            versions=[version],
            active_version_id=version_id
        )
        self.templates[name] = template
        self._save_template(template)
        logger.info("Created prompt template: %s v%s", name, version_id[:8])
        return template

    def create_version(
        self,
        template_name: str,
        new_prompt: str,
        variables: Optional[List[str]] = None,
        model_config: Optional[Dict] = None,
        created_by: str = "system"
    ) -> PromptVersion:
        template = self.templates.get(template_name)
        if not template:
            raise ValueError(f"Template {template_name} not found")

        version_id = self._hash_prompt(new_prompt)
        for v in template.versions:
            if v.id == version_id:
                raise ValueError("Identical prompt already exists")

        version = PromptVersion(
            id=version_id,
            content=new_prompt,
            template_variables=variables or [],
            model_config=model_config or {},
            created_by=created_by
        )
        template.versions.append(version)
        template.active_version_id = version_id
        self._save_template(template)
        logger.info("Created version %s for %s", version_id[:8], template_name)
        return version

    def render(
        self,
        template_name: str,
        variables: Dict[str, Any],
        version_id: Optional[str] = None
    ) -> str:
        template = self.templates.get(template_name)
        if not template:
            raise ValueError(f"Template {template_name} not found")

        version_id = version_id or template.active_version_id
        version = next(
            (v for v in template.versions if v.id == version_id),
            None
        )
        if not version:
            raise ValueError(f"Version {version_id} not found")

        missing = set(version.template_variables) - set(variables.keys())
        if missing:
            raise ValueError(f"Missing template variables: {missing}")

        prompt = version.content
        for key, value in variables.items():
            if self._detect_injection(str(value)):
                logger.warning("Potential prompt injection in variable %s", key)
                value = self._sanitize(str(value))
            prompt = prompt.replace(f"{{{key}}}", str(value))

        version.usage_count += 1
        return prompt

    def _detect_injection(self, value: str) -> bool:
        injection_patterns = [
            "ignore previous",
            "disregard",
            "system prompt",
            "system:",
            "you are now",
            "DAN",
            "jailbreak",
            "ignore all instructions"
        ]
        lower = value.lower()
        return any(p in lower for p in injection_patterns)

    def _sanitize(self, value: str) -> str:
        return value.replace("{", "{{").replace("}", "}}")

    def rollback(self, template_name: str, steps: int = 1) -> PromptVersion:
        template = self.templates.get(template_name)
        if not template:
            raise ValueError(f"Template {template_name} not found")
        if len(template.versions) <= steps:
            raise ValueError("Cannot rollback further")

        current_idx = next(
            i for i, v in enumerate(template.versions)
            if v.id == template.active_version_id
        )
        target_idx = max(0, current_idx - steps)
        target_version = template.versions[target_idx]
        template.active_version_id = target_version.id
        template.status = PromptStatus.ROLLED_BACK
        self._save_template(template)
        logger.info("Rolled back %s to %s", template_name, target_version.id[:8])
        return target_version

    def compare_versions(
        self,
        template_name: str,
        v1_id: str,
        v2_id: str
    ) -> Dict[str, Any]:
        template = self.templates[template_name]
        v1 = next(v for v in template.versions if v.id == v1_id)
        v2 = next(v for v in template.versions if v.id == v2_id)

        return {
            "v1": v1_id[:8],
            "v2": v2_id[:8],
            "v1_metrics": {
                "avg_latency_ms": v1.avg_latency_ms,
                "avg_cost": v1.avg_cost,
                "success_rate": v1.success_rate,
                "usage": v1.usage_count
            },
            "v2_metrics": {
                "avg_latency_ms": v2.avg_latency_ms,
                "avg_cost": v2.avg_cost,
                "success_rate": v2.success_rate,
                "usage": v2.usage_count
            },
            "performance_delta": {
                "latency": f"{((v2.avg_latency_ms - v1.avg_latency_ms) / max(v1.avg_latency_ms, 1)):+.1%}",
                "cost": f"{((v2.avg_cost - v1.avg_cost) / max(v1.avg_cost, 1)):+.1%}",
                "success_rate": f"{v2.success_rate - v1.success_rate:+.2%}"
            }
        }

    def auto_rollback_on_regression(
        self,
        template_name: str,
        max_latency_regression: float = 0.2,
        max_cost_regression: float = 0.3,
        min_success_rate: float = 0.95
    ) -> Optional[PromptVersion]:
        template = self.templates.get(template_name)
        if not template or len(template.versions) < 2:
            return None

        current = next(
            v for v in template.versions
            if v.id == template.active_version_id
        )
        previous = template.versions[-2]

        latency_reg = (current.avg_latency_ms - previous.avg_latency_ms) / max(previous.avg_latency_ms, 1)
        cost_reg = (current.avg_cost - previous.avg_cost) / max(previous.avg_cost, 1)

        if (latency_reg > max_latency_regression or
            cost_reg > max_cost_regression or
            current.success_rate < min_success_rate):

            logger.warning(
                "Regression detected in %s! Latency: %+.1f%%, Cost: %+.1f%%, Success: %.2f%%",
                template_name, latency_reg * 100, cost_reg * 100, current.success_rate * 100
            )
            return self.rollback(template_name, steps=1)
        return None

    def _hash_prompt(self, prompt: str) -> str:
        return hashlib.sha256(prompt.encode()).hexdigest()[:16]

    def _save_template(self, template: PromptTemplate):
        path = self.storage / f"{template.name}.json"
        with open(path, "w") as f:
            json.dump({
                "name": template.name,
                "description": template.description,
                "versions": [
                    {
                        "id": v.id,
                        "content": v.content,
                        "template_variables": v.template_variables,
                        "model_config": v.model_config,
                        "created_at": v.created_at,
                        "created_by": v.created_by,
                        "avg_latency_ms": v.avg_latency_ms,
                        "avg_cost": v.avg_cost,
                        "success_rate": v.success_rate,
                        "usage_count": v.usage_count
                    }
                    for v in template.versions
                ],
                "active_version_id": template.active_version_id,
                "status": template.status.value
            }, f, indent=2)
