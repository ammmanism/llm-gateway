"""
Fusion DAG Execution
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

logger = logging.getLogger(__name__)


class FusionStageType(Enum):
    TRANSFORM = auto()
    COMBINE = auto()
    SPLIT = auto()
    ENHANCE = auto()


@dataclass
class FusionStage:
    id: str
    stage_type: FusionStageType
    inputs: list[str]
    output_modality: str
    operation: str
    adapter: str
    params: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    can_parallelize: bool = False


@dataclass
class FusionDAG:
    stages: list[FusionStage]
    inputs: list[dict[str, Any]]
    output_modality: str

    async def execute(self, adapters: dict[str, Any]) -> Any:
        results = {}
        completed = set()

        while len(completed) < len(self.stages):
            ready = [
                s
                for s in self.stages
                if s.id not in completed and all(d in completed for d in s.dependencies)
            ]

            parallel_groups = []
            current_group = []
            for stage in ready:
                if stage.can_parallelize and current_group:
                    current_group.append(stage)
                else:
                    if current_group:
                        parallel_groups.append(current_group)
                    current_group = [stage]
            if current_group:
                parallel_groups.append(current_group)

            for group in parallel_groups:
                if len(group) == 1:
                    results[group[0].id] = await self._execute_stage(
                        group[0], adapters, results
                    )
                    completed.add(group[0].id)
                else:
                    tasks = [
                        self._execute_stage(stage, adapters, results) for stage in group
                    ]
                    stage_results = await asyncio.gather(*tasks)
                    for stage, result in zip(group, stage_results, strict=False):
                        results[stage.id] = result
                        completed.add(stage.id)

        final_stage = [
            s for s in self.stages if s.output_modality == self.output_modality
        ][-1]
        return {
            "content": results[final_stage.id],
            "stages_executed": len(self.stages),
            "providers": list(
                {
                    r.get("provider", "unknown")
                    for r in results.values()
                    if isinstance(r, dict)
                }
            ),
        }

    async def _execute_stage(
        self, stage: FusionStage, adapters: dict, prior_results: dict
    ) -> Any:
        adapter = adapters.get(stage.adapter)
        if not adapter:
            raise ValueError(f"Unknown adapter: {stage.adapter}")

        resolved_inputs = []
        for inp in stage.inputs:
            if inp in prior_results:
                resolved_inputs.append(prior_results[inp])
            else:
                resolved_inputs.append(inp)

        if stage.operation == "generate":
            return await adapter.generate(resolved_inputs, **stage.params)
        elif stage.operation == "edit":
            return await adapter.edit(*resolved_inputs, **stage.params)
        elif stage.operation == "understand":
            return await adapter.understand(*resolved_inputs, **stage.params)
        elif stage.operation == "transcribe":
            return await adapter.transcribe(*resolved_inputs, **stage.params)
        else:
            raise ValueError(f"Unknown operation: {stage.operation}")
