import json
import os
import sys

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.openapi.utils import get_openapi
from app.main import app

def export():
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    os.makedirs("docs", exist_ok=True)
    out = "docs/openapi.json"
    with open(out, "w") as f:
        json.dump(schema, f, indent=2)
    print(f"OpenAPI spec exported to {out}")

if __name__ == "__main__":
    export()
