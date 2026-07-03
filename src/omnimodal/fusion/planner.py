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
        
