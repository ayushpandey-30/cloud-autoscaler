from flask import Flask

app = Flask(__name__)
request_count = 0          # counts how many visits we've had


@app.route("/")
def home():
    global request_count
    request_count += 1
    # Do some pointless maths so each request actually uses CPU
    total = sum(i * i for i in range(200000))
    return f"Hello! Work done: {total}"


@app.route("/metrics")
def metrics():
    # The collector reads this to learn how many requests happened
    return {"requests": request_count}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)