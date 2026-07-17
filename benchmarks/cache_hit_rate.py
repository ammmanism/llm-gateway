#!/usr/bin/env python3
"""
Benchmark exact and semantic cache hit rates and cost savings.
Uses mock LLM compute with a fixed cost per query.
"""
import json
import random
import time
from pathlib import Path

QUERY_FILE = Path("benchmarks/data/queries.json")
NUM_QUERIES = 1000
COST_PER_CALL = 0.002

PARAPHRASE_PAIRS = [
    ("what is the capital of france", "tell me the capital city of france"),
    ("explain quantum computing in simple terms", "how does quantum computing work"),
    ("how to fix a leaking faucet", "repair a leaky faucet step by step"),
    ("write a python function to sort a list", "how to sort a list in python"),
    ("summarize the plot of the great gatsby", "what happens in the great gatsby"),
    ("what is machine learning", "explain how machine learning works"),
    ("best practices for rest api design", "how to design a good rest api"),
    ("difference between http and https", "compare http and https protocols"),
    ("how to optimize postgresql queries", "improve postgresql query performance"),
    ("write a dockerfile for a python app", "how to containerize a python application"),
    ("tell me about the weather in paris", "what is the weather in paris today"),
    ("how do i reset my password", "i forgot my password how to reset it"),
    ("best way to learn python", "how should i start learning python"),
    ("recommend a good book to read", "what book would you recommend"),
    ("how does photosynthesis work", "explain how photosynthesis works"),
    ("what are symptoms of the flu", "how do i know if i have the flu"),
    ("best way to cook pasta", "what is the best way to cook pasta"),
    ("what is the speed of light", "how fast does light travel"),
    ("how do i backup my iphone", "procedure to backup an iphone"),
    ("what causes earthquakes", "why do earthquakes happen"),
    ("how does blockchain technology work", "explain blockchain technology simply"),
    ("what is the stock market", "how does the stock market work"),
    ("how to meditate for beginners", "good meditation technique for beginners"),
    ("benefits of regular exercise", "why is exercise good for your health"),
    ("how to write a good resume", "what should i include in my resume"),
    ("what is climate change", "explain global warming and its effects"),
    ("how do vaccines work", "what is the mechanism of vaccines"),
    ("what is the meaning of life", "what is the purpose of human existence"),
    ("how to get better at chess", "tips to improve my chess game"),
    ("what is seo optimization", "explain seo and search engine optimization"),
    ("how to bake a chocolate cake", "recipe for chocolate cake"),
    ("what is artificial intelligence", "explain ai and its applications"),
    ("how to invest in stocks", "beginner guide to stock investing"),
    ("benefits of drinking green tea", "green tea benefits for health"),
    ("how to learn a new language", "best ways to learn a foreign language"),
    ("what is the solar system", "explain the planets in our solar system"),
    ("how to start a blog", "steps to begin blogging"),
    ("what causes global warming", "main reasons for climate change"),
    ("how to improve memory", "techniques to boost memory retention"),
    ("what is cryptocurrency", "explain how bitcoin and crypto work"),
    ("how to grow tomatoes", "tips for planting tomato seeds"),
    ("what is the human genome", "explain dna and genetic sequencing"),
    ("how to tie a tie", "steps to knot a necktie"),
    ("benefits of meditation", "why should you meditate daily"),
    ("how to change a tire", "steps to replace a flat tire"),
    ("what is the water cycle", "explain how water circulates in nature"),
    ("how to build a pc", "guide to assembling a computer"),
    ("what are antioxidants", "explain the role of antioxidants in body"),
    ("how to do a push up", "proper form for doing push ups"),
    ("what is a black hole", "explain black holes in astronomy"),
    ("how to make sourdough bread", "recipe for homemade sourdough"),
    ("what is the internet of things", "explain iot and its applications"),
    ("how to study effectively", "best study techniques for students"),
    ("benefits of yoga", "why yoga is good for your body"),
    ("how to reduce stress", "natural ways to relieve stress"),
]

def load_queries():
    seen = set()
    def unique(q):
        if q not in seen:
            seen.add(q)
            return True
        return False

    queries = []
    random.shuffle(PARAPHRASE_PAIRS)
    for a, b in PARAPHRASE_PAIRS:
        if unique(a) and unique(b):
            queries.append(a)
            queries.append(b)
    for i in range(NUM_QUERIES - len(queries)):
        queries.append("qx_" + str(i) + "_" + str(hex(abs(hash(str(i)))))[2:10])
    random.shuffle(queries)
    return queries[:NUM_QUERIES]

def compute_fn(query):
    time.sleep(0.01)
    return {"response": f"Response to {query}"}

class NoCache:
    def get_or_compute(self, query, compute_fn):
        return type('', (), {'was_cached': False, 'estimated_cost': 0})()

class ExactCache:
    def __init__(self):
        self.cache = {}
    def get_or_compute(self, query, compute_fn):
        if query in self.cache:
            return type('', (), {'was_cached': True, 'estimated_cost': 0})()
        self.cache[query] = compute_fn(query)
        return type('', (), {'was_cached': False, 'estimated_cost': 0})()

class SemanticCache:
    def __init__(self, threshold=0.92):
        self.cache = {}
        self.threshold = threshold
    def get_or_compute(self, query, compute_fn):
        for cached_query in self.cache:
            similarity = self._cosine_similarity(query, cached_query)
            if similarity >= self.threshold:
                return type('', (), {'was_cached': True, 'estimated_cost': 0})()
        self.cache[query] = compute_fn(query)
        return type('', (), {'was_cached': False, 'estimated_cost': 0})()
    def _cosine_similarity(self, a, b):
        tokens_a = a.lower().split()
        tokens_b = b.lower().split()
        if not tokens_a or not tokens_b:
            return 0.0
        from collections import Counter
        vec_a = Counter(tokens_a)
        vec_b = Counter(tokens_b)
        dot = sum(vec_a[k] * vec_b.get(k, 0) for k in vec_a)
        norm_a = sum(v*v for v in vec_a.values()) ** 0.5
        norm_b = sum(v*v for v in vec_b.values()) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

def run_benchmark(queries, cache):
    hits = 0
    cost_saved = 0.0
    start = time.perf_counter()
    for q in queries:
        result = cache.get_or_compute(q, compute_fn=compute_fn)
        if result.was_cached:
            hits += 1
            cost_saved += COST_PER_CALL
    elapsed = time.perf_counter() - start
    return {
        "hit_rate": round(hits / len(queries), 4),
        "cost_saved_usd": round(cost_saved, 4),
        "queries": len(queries),
        "elapsed_seconds": round(elapsed, 2),
    }

if __name__ == "__main__":
    queries = load_queries()
    results = {
        "no_cache": run_benchmark(queries, NoCache()),
        "exact_cache": run_benchmark(queries, ExactCache()),
        "semantic_cache": run_benchmark(queries, SemanticCache(threshold=0.4)),
    }
    out_file = Path("benchmarks/results/cache_comparison.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results, indent=2))
