"""
Directed Acyclic Graph structures for Cross-Modal Fusion
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
from enum import Enum, auto


class FusionStageType(Enum):
    TRANSFORM = auto()      # Single modality -> single modality
    COMBINE = auto()        # Multiple modalities -> single modality
    SPLIT = auto()          # Single modality -> multiple modalities
    ENHANCE = auto()       # Same modality, quality improvement


@dataclass
class FusionStage:
    id: str
    stage_type: FusionStageType
    inputs: List[str]        # Stage IDs or raw inputs
    output_modality: str
    operation: str
    adapter: str
    params: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    can_parallelize: bool = False
