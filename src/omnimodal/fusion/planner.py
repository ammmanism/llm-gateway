"""
Fusion Planner
Creates Directed Acyclic Graphs of fusion operations.
"""

from typing import List, Dict, Any, Optional
from omnimodal.fusion.dag import FusionStage, FusionStageType
from omnimodal.fusion.engine import FusionDAG


class FusionPlanner:
    """
    Automatically plans optimal fusion pipelines.
    """
    
    def __init__(self):
        self.transformation_rules = self._init_rules()
    
    def _init_rules(self) -> Dict[str, List[str]]:
        """Define allowed modality transformations."""
        return {
            "text": ["text", "image", "audio"],
            "image": ["text", "image", "video"],
            "audio": ["text", "audio"],
            "video": ["text", "image", "audio", "video"],
        }
    
    def plan(
        self,
        inputs: List[Dict[str, Any]],
        output_modality: str,
        constraints: Optional[Dict] = None
    ) -> FusionDAG:
        """
        Create an optimal fusion DAG.
        """
        constraints = constraints or {}
        # Convert dictionary inputs to list of types
        input_modalities = [inp.get("type", "text") if isinstance(inp, dict) else getattr(inp, "type", "text") for inp in inputs]
        
        # Simple case: direct generation
        if len(input_modalities) == 1 and input_modalities[0] == output_modality:
            return self._plan_direct(inputs, output_modality, constraints)
        
        # Complex case: multimodal fusion
        if output_modality == "video" and "image" in input_modalities:
            return self._plan_image_to_video(inputs, constraints)
        
        if output_modality == "text" and "video" in input_modalities:
            return self._plan_video_to_text(inputs, constraints)
        
        if output_modality == "multimodal":
            return self._plan_multimodal_output(inputs, constraints)
        
        # Generic plan
        return self._plan_generic(inputs, output_modality, constraints)
    
    def _plan_direct(self, inputs, output_modality, constraints) -> FusionDAG:
        """Single modality direct generation."""
        adapter_map = {"text": "text", "image": "image", "audio": "audio", "video": "video"}
        
        return FusionDAG(
            stages=[
                FusionStage(
                    id="stage_1",
                    stage_type=FusionStageType.TRANSFORM,
                    inputs=["raw_input"],
                    output_modality=output_modality,
                    operation="generate",
                    adapter=adapter_map.get(output_modality, "text"),
