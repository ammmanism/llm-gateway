import json
from src.main import app
from fastapi.openapi.utils import get_openapi

def export_openapi():
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )
    with open("docs/openapi.json", "w") as f:
        json.dump(openapi_schema, f, indent=2)
    print("Successfully exported OpenAPI spec to docs/openapi.json")

if __name__ == "__main__":
    export_openapi()