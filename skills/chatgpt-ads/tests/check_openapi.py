"""Compare the public command surface with a downloaded official Ads OpenAPI file."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from chatgpt_ads import handle, parser


def audit(document):
    cli = parser()
    commands = handle(cli.parse_args(["operations"]))
    routes = {}
    for name in commands:
        action = handle(cli.parse_args(["describe", name]))
        route = (action["method"], action["path"])
        if route in routes:
            raise ValueError(f"Duplicate command for {route}")
        routes[route] = action
    schemas = document["components"]["schemas"]
    seen = set()
    errors = []
    for path, methods in document["paths"].items():
        for method, operation in methods.items():
            if method not in ("get", "post", "put", "patch", "delete", "options", "head", "trace"):
                continue
            route = (method.upper(), path)
            seen.add(route)
            if route not in routes:
                errors.append(f"Missing {route}")
                continue
            cmd = routes[route]
            params = methods.get("parameters", []) + operation.get("parameters", [])
            expected_path = {p["name"] for p in params if p["in"] == "path"}
            if expected_path != set(cmd["path_parameters"]):
                errors.append(f"{route} path parameters")
            query = [p for p in params if p["in"] == "query"]
            if {p["name"] for p in query if p.get("required")} != set(cmd.get("required_query", [])):
                errors.append(f"{route} required query parameters")
            for param in query:
                schema = param["schema"]
                if "$ref" in schema:
                    schema = schemas[schema["$ref"].split("/")[-1]]
                if cmd.get("query", {}).get(param["name"]) != schema.get("type", "value"):
                    errors.append(f"{route} query parameter {param['name']}")
            if any(p["name"] == "Idempotency-Key" for p in params) and not cmd.get("idempotent"):
                errors.append(f"{route} idempotency header")
            for content in operation.get("requestBody", {}).get("content", {}).values():
                schema = content["schema"]
                if "$ref" in schema:
                    schema = schemas[schema["$ref"].split("/")[-1]]
                if set(schema.get("properties", {})) - set(cmd.get("fields", [])):
                    errors.append(f"{route} missing body fields")
                if set(schema.get("required", [])) != set(cmd.get("required", [])):
                    errors.append(f"{route} required body fields")
    if errors:
        raise ValueError("\n".join(errors))
    return {
        "spec_version": document["info"]["version"],
        "official_paths": len({path for _, path in seen}),
        "official_operations": len(seen),
        "matched_operations": len(seen & routes.keys()),
        "missing_operations": 0,
        "additional_operations": len(routes.keys() - seen),
        "named_operations": len(commands),
        "read": sum(access == "read" for access in commands.values()),
        "plan": sum(access == "plan" for access in commands.values()),
    }


if __name__ == "__main__":
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("openapi", type=Path)
    print(json.dumps(audit(json.loads(args.parse_args().openapi.read_bytes())), indent=2))
