"""Run one bounded provider decision with synthetic facts, without printing credentials."""

import argparse
import asyncio
import json

import httpx

from app import support_ai


async def check(provider: str, model: str) -> int:
    if not support_ai.configured(provider, model) or provider not in support_ai.PROVIDERS:
        print(json.dumps({"provider": provider, "model": model, "configured": False}))
        return 2
    question = "What is the price of the Synthetic Test Rack?"
    messages = [{"role": "user", "text": question}]
    catalog = [{
        "ref": "product:1", "type": "product", "id": 1, "name": "Synthetic Test Rack",
        "category": "Racks", "price": 123.45, "currency": "CAD",
        "publicationStatus": "published", "description": "A synthetic fixture, not a real product.",
    }]
    topics = ["products", "pricing", "compatibility"]
    evidence = support_ai.retrieve_catalog(support_ai.public_evidence(catalog, topics), question, question, None)
    try:
        decision, usage = await support_ai.PROVIDERS[provider]().decide(messages, evidence, topics, model)
        answer = support_ai.render(decision, evidence, topics, question, usage)
        valid = not answer.needs_human and answer.topic == "pricing" and "CAD $123.45" in answer.text and answer.references == ("product:1",)
        print(json.dumps({"provider": provider, "model": model, "providerDecisionVerified": valid,
                          "reason": answer.reason, "usage": usage, "syntheticOnly": True}))
        return 0 if valid else 1
    except (ValueError, OSError, TimeoutError, KeyError, TypeError, httpx.HTTPError) as error:
        print(json.dumps({"provider": provider, "model": model, "providerDecisionVerified": False,
                          "errorType": type(error).__name__, "syntheticOnly": True}))
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("openai", "gemini"), default="openai")
    parser.add_argument("--model", required=True)
    arguments = parser.parse_args()
    return asyncio.run(check(arguments.provider, arguments.model))


if __name__ == "__main__":
    raise SystemExit(main())
