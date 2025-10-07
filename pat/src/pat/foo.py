import redis

def hello_redis():
    # Connect to Redis
    # Replace 'localhost' and 6379 if your Redis server is elsewhere
    # decode_responses=True converts Redis responses to Python strings
    r = redis.StrictRedis(host='localhost', port=6379, decode_responses=True)

    # Set a key-value pair
    r.set("msg:hello", "Hello Redis!!!")

    # Retrieve the value
    msg = r.get("msg:hello")
    print(msg)

if __name__ == '__main__':
    hello_redis()
