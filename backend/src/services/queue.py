"""Redis queue keys shared by the API and the independent worker."""
import redis
from src.config.settings import REDIS_URL

RUNS='package-criticality:jobs'
CHECKPOINTS='package-criticality:checkpoints'

def enqueue(key,id):
 redis.Redis.from_url(REDIS_URL).lpush(key,id)
