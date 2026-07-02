import itertools

class LoadBalancer:
    """
    Simple round-robin load balancer for equivalent providers/endpoints if we had multiple keys.
    Not strictly needed for basic routing, but good to have the structure.
    """
    def __init__(self, items):
        self._items = items
        self._cycle = itertools.cycle(items)
        
    def next(self):
        if not self._items:
            return None
        return next(self._cycle)