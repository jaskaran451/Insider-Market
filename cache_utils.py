import os
import json
import time

BASE_CACHE = "cache"
def get_cache_path(category, symbol):
    folder = os.path.join(BASE_CACHE, category)
    os.makedirs(folder, exist_ok=True)

    return os.path.join(folder, f"{symbol}.json")


def load_cache(folder, key, max_age_seconds=3600):
    path = get_cache_path(folder, key)

    if not os.path.exists(path):
        return None

    with open(path, "r") as f:
        data = json.load(f)

    # safety check (VERY IMPORTANT)
    if "timestamp" not in data:
        return None
    if time.time() - float(data["timestamp"]) > max_age_seconds:
        return None


    return data["payload"]

def save_cache(folder, key, payload):
    path = get_cache_path(folder, key)

    data = {
        "timestamp": time.time(),
        "payload": payload
    }

    with open(path, "w") as f:
        json.dump(data, f)