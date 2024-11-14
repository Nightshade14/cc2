from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    redirect,
    url_for,
)  # For flask implementation
from pymongo import MongoClient  # Database connector
from pymongo.errors import ConnectionFailure
from bson.objectid import ObjectId  # For ObjectId to work
from bson.errors import InvalidId  # For catching InvalidId exception for ObjectId
import os
from prometheus_flask_exporter import PrometheusMetrics

mongodb_host = os.environ.get("MONGO_HOST", "localhost")
mongodb_port = int(os.environ.get("MONGO_PORT", "27017"))
client = MongoClient(
    mongodb_host, mongodb_port
)  # Configure the connection to the database
db = client.camp2016  # Select the database
todos = db.todo  # Select the collection

app = Flask(__name__)
title = "TODO with Flask"
heading = "ToDo Reminder:V3"
# modify=ObjectId()

a2 = "active"
metrics = PrometheusMetrics(app)

# Custom metrics
metrics.info("todo_app_info", "Application information", version="1.0.0")
todo_items_total = metrics.counter("todo_items_total", "Number of todo items created")
mongodb_operations = metrics.counter(
    "mongodb_operations_total", "Number of MongoDB operations"
)

mongodb_connection_failures = metrics.counter(
    "mongodb_connection_failures_total", "Number of MongoDB connection failures"
)


def redirect_url():
    return request.args.get("next") or request.referrer or url_for("index")


# liveness probe endpoint
@app.route("/health")
@metrics.counter("health_check_requests_total", "Number of health check requests")
def healthz():
    # This endpoint returns a simple 200 OK response to indicate that the app is alive
    return jsonify(status="alive"), 200


# Readiness probe endpoint
@app.route("/ready")
@metrics.counter(
    "readiness_check_total",
    "Number of readiness checks",
    labels={"status": lambda r: str(r.status_code)},
)
def ready():
    try:
        client.admin.command("ping")
        return jsonify(status="ready"), 200
    except ConnectionFailure:
        # If there's a connection failure, return a 503 Service Unavailable status
        mongodb_connection_failures.inc()
        return jsonify(status="unready"), 503


@app.route("/list")
def lists():
    # Display the all Tasks
    todos_l = todos.find()
    a1 = "active"
    return render_template("index.html", a1=a1, todos=todos_l, t=title, h=heading)


@app.route("/")
@app.route("/uncompleted")
def tasks():
    # Display the Uncompleted Tasks
    todos_l = todos.find({"done": "no"})
    a2 = "active"
    return render_template("index.html", a2=a2, todos=todos_l, t=title, h=heading)


@app.route("/completed")
def completed():
    # Display the Completed Tasks
    todos_l = todos.find({"done": "yes"})
    a3 = "active"
    return render_template("index.html", a3=a3, todos=todos_l, t=title, h=heading)


@app.route("/done")
def done():
    # Done-or-not ICON
    id = request.values.get("_id")
    task = todos.find({"_id": ObjectId(id)})
    if task[0]["done"] == "yes":
        todos.update_one({"_id": ObjectId(id)}, {"$set": {"done": "no"}})
    else:
        todos.update_one({"_id": ObjectId(id)}, {"$set": {"done": "yes"}})
    redir = (
        redirect_url()
    )  # Re-directed URL i.e. PREVIOUS URL from where it came into this one

    # if(str(redir)=="http://localhost:5000/search"):
    # redir+="?key="+id+"&refer="+refer

    return redirect(redir)


# @app.route("/add")
# def add():
# return render_template('add.html',h=heading,t=title)


@app.route("/action", methods=["POST"])
def action():
    # Adding a Task
    name = request.values.get("name")
    desc = request.values.get("desc")
    date = request.values.get("date")
    pr = request.values.get("pr")
    try:
        todos.insert_one(
            {"name": name, "desc": desc, "date": date, "pr": pr, "done": "no"}
        )
        todo_items_total.inc()
        mongodb_operations.labels(operation_type="create").inc()
        return redirect("/list")
    except Exception:
        return jsonify({"error": "Failed to create todo"}), 500


@app.route("/remove")
def remove():
    # Deleting a Task with various references
    key = request.values.get("_id")
    try:
        todos.delete_one({"_id": ObjectId(key)})
        mongodb_operations.labels(operation_type="delete").inc()
        return redirect("/")
    except Exception:
        return jsonify({"error": "Failed to delete todo"}), 500


@app.route("/update")
def update():
    id = request.values.get("_id")
    task = todos.find({"_id": ObjectId(id)})
    return render_template("update.html", tasks=task, h=heading, t=title)


@app.route("/action3", methods=["POST"])
def action3():
    # Updating a Task with various references
    name = request.values.get("name")
    desc = request.values.get("desc")
    date = request.values.get("date")
    pr = request.values.get("pr")
    id = request.values.get("_id")
    todos.update_one(
        {"_id": ObjectId(id)},
        {"$set": {"name": name, "desc": desc, "date": date, "pr": pr}},
    )
    return redirect("/")


@app.route("/search", methods=["GET"])
def search():
    # Searching a Task with various references

    key = request.values.get("key")
    refer = request.values.get("refer")
    if refer == "id":
        try:
            todos_l = todos.find({refer: ObjectId(key)})
            if not todos_l:
                return render_template(
                    "index.html",
                    a2=a2,
                    todos=todos_l,
                    t=title,
                    h=heading,
                    error="No such ObjectId is present",
                )
        except InvalidId as err:
            return render_template(
                "index.html",
                a2=a2,
                todos=todos_l,
                t=title,
                h=heading,
                error="Invalid ObjectId format given: " + str(err),
            )
    else:
        todos_l = todos.find({refer: key})
    return render_template("searchlist.html", todos=todos_l, t=title, h=heading)


@app.route("/about")
def about():
    return render_template("credits.html", t=title, h=heading)


if __name__ == "__main__":
    env = os.environ.get("FLASK_ENV", "production")
    port = int(os.environ.get("PORT", 5000))
    app.run(port=port, debug=False)
