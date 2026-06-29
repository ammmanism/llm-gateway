import time
from src.router.smart_router import smart_router

def run_benchmark():
    num_routes = 10000
    
    print(f"Running {num_routes} routing decisions...")
    start = time.time()
    
    for _ in range(num_routes):
        # Simulate varying token counts
        smart_router.route(request_tokens=500)
        
    end = time.time()
    duration = end - start
    
    print(f"Total time: {duration:.4f}s")
    print(f"Average latency per route: {(duration/num_routes)*1000:.4f}ms")
    print(f"Throughput: {num_routes/duration:.2f} routes/sec")

if __name__ == "__main__":
    run_benchmark()
