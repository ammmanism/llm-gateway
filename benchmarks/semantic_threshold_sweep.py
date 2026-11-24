"""Sweep the semantic-cache similarity threshold on a labelled prompt set.

For each threshold we add one anchor prompt per intent to the real
`SemanticIndex` (FAISS HNSW, cosine via inner product on normalized vectors),
then replay paraphrase queries (which *should* hit their own intent) and
distractor queries (which should *not* hit anything).

Reported per threshold:
* hit_rate            - paraphrases that returned the correct intent
* false_positive_rate - distractors that wrongly returned any intent
* wrong_intent_rate   - paraphrases that matched a *different* intent
* precision           - correct hits / all semantic hits
"""

import asyncio
import csv
import statistics
from pathlib import Path

from llm_gateway.cache.two_tier import SemanticIndex
from llm_gateway.utils.embeddings import embedding_engine

THRESHOLDS = [0.80, 0.85, 0.90, 0.95]
OUTPUT = Path("data/evidence/semantic_threshold_sweep.csv")
NAMESPACE = "sweep"
NOW = 1_000_000.0
TTL = 10**9

DATASET = {
    "capital_france": {
        "anchor": "What is the capital of France?",
        "paraphrases": [
            "Which city is the capital of France?",
            "What's France's capital city?",
        ],
    },
    "sourdough": {
        "anchor": "How do I bake sourdough bread at home?",
        "paraphrases": [
            "Give me a beginner sourdough bread recipe.",
            "Steps to make sourdough bread from scratch.",
        ],
    },
    "contract_summary": {
        "anchor": "Summarize this contract in plain English.",
        "paraphrases": [
            "Explain this legal agreement simply.",
            "Give me a plain-language summary of this contract.",
        ],
    },
    "quicksort": {
        "anchor": "Write a Python implementation of quicksort.",
        "paraphrases": [
            "Show me quicksort code in Python.",
            "Implement the quicksort algorithm using Python.",
        ],
    },
    "jwt_expiry": {
        "anchor": "How do I set a JWT expiration time?",
        "paraphrases": [
            "Configure token expiry for a JSON Web Token.",
            "Set the exp claim when creating a JWT.",
        ],
    },
    "sql_index": {
        "anchor": "Why is my SQL query slow without an index?",
        "paraphrases": [
            "Explain how missing database indexes slow down queries.",
            "My Postgres query is slow, should I add an index?",
        ],
    },
    "docker_port": {
        "anchor": "How do I expose a port in a Docker container?",
        "paraphrases": [
            "Map a host port to a container port in Docker.",
            "Publish container ports with docker run.",
        ],
    },
    "git_undo": {
        "anchor": "How do I undo the last git commit?",
        "paraphrases": [
            "Revert my most recent commit in git.",
            "Take back the last commit without losing changes.",
        ],
    },
    "sleep_hygiene": {
        "anchor": "What are good sleep hygiene habits?",
        "paraphrases": [
            "How can I improve my sleep quality?",
            "Tips for sleeping better at night.",
        ],
    },
    "mortgage": {
        "anchor": "How is a fixed-rate mortgage calculated?",
        "paraphrases": [
            "Explain fixed-rate mortgage payments.",
            "How do fixed interest mortgage repayments work?",
        ],
    },
    "kubernetes_probe": {
        "anchor": "What is a Kubernetes liveness probe?",
        "paraphrases": [
            "Explain liveness probes in Kubernetes.",
            "How does the k8s liveness check work?",
        ],
    },
    "password_hash": {
        "anchor": "How should I hash passwords securely?",
        "paraphrases": [
            "Best way to store hashed passwords.",
            "What algorithm should I use to hash user passwords?",
        ],
    },
}

# Unrelated domains: should never hit any anchor.
UNRELATED_DISTRACTORS = [
    "What is the weather in Tokyo tomorrow?",
    "Recommend a good science fiction novel.",
    "How do I change a car tire?",
    "What caused the French Revolution?",
    "Translate 'good morning' into Japanese.",
    "How many calories are in a banana?",
    "Explain quantum entanglement in simple terms.",
    "What is the best way to train for a marathon?",
    "Who painted the Mona Lisa?",
    "How do I fix a leaking kitchen faucet?",
    "What are the rules of cricket?",
    "Suggest a weekly meal plan for a vegetarian.",
]

# Near-domain but different-intent queries. A semantic cache that answers any of
# these with a stored anchor would return the *wrong* answer, so they count as
# false positives even though the wording is close.
HARD_NEGATIVES = [
    "What is the capital of Germany?",
    "What is the population of Paris?",
    "How do I make a sourdough starter?",
    "What is the difference between quicksort and mergesort?",
    "How do I refresh an expired JWT?",
    "What is a database primary key?",
    "How do I build a Docker image?",
    "How do I squash several git commits into one?",
    "How much sleep do teenagers need?",
    "What is an adjustable-rate mortgage?",
    "What is a Kubernetes readiness probe?",
    "What is password salting?",
]


async def main() -> None:
    embedding_engine.load()
    print(f"embedding backend: {embedding_engine.backend_name}")

    index = SemanticIndex(embedder=embedding_engine)
    for intent, spec in DATASET.items():
        await index.add(
            NAMESPACE,
            spec["anchor"],
            {"intent": intent},
            TTL,
            NOW,
        )

    rows = []
    for threshold in THRESHOLDS:
        correct = 0
        wrong = 0
        missed = 0
        correct_similarities = []
        total_paraphrases = 0

        for intent, spec in DATASET.items():
            for query in spec["paraphrases"]:
                total_paraphrases += 1
                result = await index.search(NAMESPACE, query, threshold, NOW)
                if result is None:
                    missed += 1
                elif result.value["intent"] == intent:
                    correct += 1
                    correct_similarities.append(result.similarity)
                else:
                    wrong += 1

        false_positives = 0
        for query in UNRELATED_DISTRACTORS:
            result = await index.search(NAMESPACE, query, threshold, NOW)
            if result is not None:
                false_positives += 1

        hard_negative_hits = 0
        for query in HARD_NEGATIVES:
            result = await index.search(NAMESPACE, query, threshold, NOW)
            if result is not None:
                hard_negative_hits += 1

        hits = correct + wrong
        total_distractors = len(UNRELATED_DISTRACTORS) + len(HARD_NEGATIVES)
        rows.append(
            {
                "threshold": f"{threshold:.2f}",
                "paraphrase_queries": total_paraphrases,
                "correct_intent_hits": correct,
                "wrong_intent_hits": wrong,
                "missed": missed,
                "hit_rate": round(correct / total_paraphrases, 4),
                "unrelated_queries": len(UNRELATED_DISTRACTORS),
                "unrelated_false_positives": false_positives,
                "hard_negative_queries": len(HARD_NEGATIVES),
                "hard_negative_false_positives": hard_negative_hits,
                "false_positive_queries": total_distractors,
                "false_positive_hits": false_positives + hard_negative_hits,
                "false_positive_rate": round(
                    (false_positives + hard_negative_hits) / total_distractors, 4
                ),
                "hard_negative_false_positive_rate": round(
                    hard_negative_hits / len(HARD_NEGATIVES), 4
                ),
                "wrong_intent_rate": round(wrong / total_paraphrases, 4),
                "precision": round(correct / hits, 4) if hits else 1.0,
                "mean_correct_similarity": (
                    round(statistics.mean(correct_similarities), 4)
                    if correct_similarities
                    else 0.0
                ),
            }
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    for row in rows:
        print(row)
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(main())
