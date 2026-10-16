from redis import Redis
from rq import Worker, Queue
from app.config import settings

if __name__ == "__main__":
    connection = Redis.from_url(settings().redis_url)
    Worker([Queue("campusmind", connection=connection), Queue("campusmind-ai", connection=connection)], connection=connection).work()
