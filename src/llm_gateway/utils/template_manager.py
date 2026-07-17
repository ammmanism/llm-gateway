import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TemplateManager:
    def __init__(self):
        self._templates: Dict[str, str] = {}

    def add_template(self, template_id: str, content: str):
        self._templates[template_id] = content
        logger.info(f"Template '{template_id}' stored")

    def render(self, template_id: str, variables: Optional[Dict[str, str]] = None) -> str:
        content = self._templates.get(template_id)
        if content is None:
            raise ValueError(f"Template '{template_id}' not found")
        if variables:
            return content.format(**variables)
        return content


template_manager = TemplateManager()
