"""Check Gemini access without printing credentials or sending customer data."""

import argparse
import asyncio
import json
import os
import re

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", help="Optional model ID for one small, synthetic generation test.")
    parser.add_argument("--support", action="store_true", help="Test the real support adapter with synthetic public facts only.")
    args = parser.parse_args()
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        print("Gemini key is not loaded into this process.")
        return 2
    if args.model and not re.fullmatch(r"gemini-[a-zA-Z0-9._-]{1,100}", args.model):
        print("Use an explicit Gemini model ID without a URL or query string.")
        return 2
    if args.support:
        if not args.model:
            print("--support requires --model.")
            return 2
        from app.support_ai import respond
        result = asyncio.run(respond(
            [{"role": "user", "text": "What is the price of the Synthetic Test Rack?"}],
            [{"ref": "product:1", "type": "product", "id": 1, "name": "Synthetic Test Rack",
              "category": "Racks", "price": 123.45, "currency": "CAD", "publicationStatus": "published",
              "description": "A synthetic testing fixture, not a real product."}],
            ["products", "pricing", "compatibility"], "gemini", args.model,
        ))
        valid = not result.needs_human and result.topic == "pricing" and "CAD $123.45" in result.text and result.references == ("product:1",)
        print(json.dumps({"supportAdapterVerified": valid, "model": args.model, "reason": result.reason,
                          "references": result.references, "usage": result.usage}))
        return 0 if valid else 1
    try:
        with httpx.Client(
            base_url="https://generativelanguage.googleapis.com/v1beta/",
            headers={"x-goog-api-key": key}, timeout=20, follow_redirects=False,
        ) as client:
            response = client.get("models", params={"pageSize": 100})
            if response.status_code != 200:
                print(json.dumps({"authenticated": False, "stage": "list_models", "httpStatus": response.status_code}))
                return 1
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
                raise ValueError("Invalid model-list response.")
            models = [item["name"].removeprefix("models/") for item in payload["models"]
                      if isinstance(item, dict) and isinstance(item.get("name"), str)
                      and item["name"].startswith("models/gemini-")
                      and "generateContent" in item.get("supportedGenerationMethods", [])]
            print(json.dumps({"authenticated": True, "models": models, "morePages": bool(payload.get("nextPageToken"))}))
            if not args.model:
                return 0
            if args.model not in models:
                print("Requested model is not in the returned model page; generation was not attempted.")
                return 1
            response = client.post(f"models/{args.model}:generateContent", json={
                "contents": [{"role": "user", "parts": [{"text": "Reply only with OK. This is a synthetic connectivity test."}]}],
                "generationConfig": {"maxOutputTokens": 256},
            })
            if response.status_code != 200:
                print(json.dumps({"generated": False, "stage": "synthetic_generation", "httpStatus": response.status_code}))
                return 1
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("candidates"), list):
                raise ValueError("Invalid generation response.")
            text = "".join(
                part["text"] for candidate in payload["candidates"] if isinstance(candidate, dict)
                for part in candidate.get("content", {}).get("parts", [])
                if isinstance(part, dict) and isinstance(part.get("text"), str) and not part.get("thought")
            )
            success = text.strip().rstrip(".!").upper() == "OK"
            reasons = [candidate.get("finishReason") for candidate in payload["candidates"] if isinstance(candidate, dict)]
            usage = payload.get("usageMetadata", {})
            token_counts = {name: value for name, value in usage.items() if name.endswith("TokenCount") and type(value) is int} if isinstance(usage, dict) else {}
            print(json.dumps({"generated": success, "model": args.model, "responseCharacters": len(text),
                              "finishReasons": reasons, "tokens": token_counts}))
            return 0 if success else 1
    except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
        print("Gemini access check failed; private response contents and credentials were not logged.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
