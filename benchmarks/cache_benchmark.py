import asyncio
import time
from src.cache.semantic import SemanticCache
from src.utils.embeddings import embedding_engine
import numpy as np
import uuid

async def run_benchmark():
    cache = SemanticCache()
    # Mocking initialization for benchmark
    cache.dimension = 384
    import faiss
    cache.index = faiss.IndexIDMap(faiss.IndexHNSWFlat(384, 32, faiss.METRIC_INNER_PRODUCT))
    
    # Pre-populate with dummy vectors
    num_vectors = 10000
    print(f"Generating {num_vectors} dummy vectors...")
    dummy_vectors = np.random.rand(num_vectors, 384).astype('float32')
    # L2 normalize
    faiss.normalize_L2(dummy_vectors)
    ids = np.arange(num_vectors)
    cache.index.add_with_ids(dummy_vectors, ids)
    
    # Create id_map
    for i in range(num_vectors):
        cache.id_map[i] = str(uuid.uuid4())
        
    print(f"Added {cache.index.ntotal} vectors to FAISS index.")
    
    # Query performance
    num_queries = 1000
    query_vectors = np.random.rand(num_queries, 384).astype('float32')
    faiss.normalize_L2(query_vectors)
    
    print(f"Running {num_queries} queries...")
    start = time.time()
    
    # Sequential search simulating individual requests
    for i in range(num_queries):
        # We search directly via FAISS to bypass redis overhead for this pure vector benchmark
        cache.index.search(np.array([query_vectors[i]]), k=5)
        
    end = time.time()
    duration = end - start
    print(f"Total time: {duration:.4f}s")
    print(f"Average latency per query: {(duration/num_queries)*1000:.2f}ms")
    print(f"Throughput: {num_queries/duration:.2f} QPS")

if __name__ == "__main__":
    asyncio.run(run_benchmark())