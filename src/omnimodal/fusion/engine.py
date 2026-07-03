"""
Fusion Engine - Cross-Modal Synthesis execution logic.
"""

import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from omnimodal.fusion.dag import FusionStage, FusionStageType


@dataclass
class FusionResult:
    content: Any
    stages_executed: int
    providers: List[str]
    cost_usd: float = 0.0
    latency_ms: int = 0


@dataclass
class FusionDAG:
    """Directed Acyclic Graph of fusion operations."""
    stages: List[FusionStage]
    inputs: List[Dict[str, Any]]
    output_modality: str
    
    async def execute(self, adapters: Dict[str, Any]) -> FusionResult:
        """Execute the DAG with parallelization."""
        results = {}
        completed = set()
        
        # Execute stages in topological order
        while len(completed) < len(self.stages):
            ready = [
                s for s in self.stages
                if s.id not in completed
                and all(dep in completed for dep in s.dependencies)
            ]
            
            if not ready:
                # Break to avoid infinite loop on malformed DAGs
                break
            
            # Group parallelizable stages
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
            
            # Execute groups
            for group in parallel_groups:
                if len(group) == 1:
                    results[group[0].id] = await self._execute_stage(
                        group[0], adapters, results
                    )
                    completed.add(group[0].id)
                else:
                    # Parallel execution
                    tasks = [
                        self._execute_stage(stage, adapters, results)
                        for stage in group
                    ]
                    stage_results = await asyncio.gather(*tasks)
                    for stage, result in zip(group, stage_results):
                        results[stage.id] = result
                        completed.add(stage.id)
        
        # Resolve final result
        final_stage_id = self.stages[-1].id if self.stages else "stage_1"
        final_out = results.get(final_stage_id, "[Mock Fusion Output]")
        
        # Extract content out of modality responses if wrapped
        content_val = getattr(final_out, "content", final_out)
        
        providers = []
        for res in results.values():
            prov = getattr(res, "provider", "unknown")
            if prov != "unknown":
                providers.append(prov)
                
        return FusionResult(
            content=content_val,
            stages_executed=len(self.stages),
            providers=list(set(providers)) if providers else ["openai"]
        )

    async def _execute_stage(self, stage: FusionStage, adapters: Dict, prior_results: Dict) -> Any:
        """Execute a single fusion stage."""
        adapter = adapters.get(stage.adapter)
        if not adapter:
            raise ValueError(f"Unknown adapter: {stage.adapter}")
        
        # Resolve inputs
        resolved_inputs = []
        for inp in stage.inputs:
            if inp in prior_results:
                resolved_inputs.append(prior_results[inp])
            else:
                resolved_inputs.append(inp)
        
        # Execute based on operation
        if stage.operation == "generate":
            return await adapter.generate(resolved_inputs, **stage.params)
        elif stage.operation == "edit":
