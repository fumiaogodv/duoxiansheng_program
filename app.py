from flask import Flask, request, jsonify, render_template,redirect,url_for
from tasks import celery, long_task

app = Flask(__name__)

@app.route("/")
def main():
    return render_template("index.html")
@app.route("/start_task", methods=["POST","GET"])
def start_task():
    if request.method=="POST":
        x = int(request.form.get("x", 0))
        y = int(request.form.get("y", 0))
        task = long_task.delay(x, y)
        return redirect(url_for('task_status', task_id=task.id))
    return render_template("count.html")
@app.route("/task_status/<task_id>")
def task_status(task_id):
    task = long_task.AsyncResult(task_id)
    return render_template("state.html",state=task.state,result=task.result)
    return jsonify({"state": task.state, "result": task.result})

if __name__ == "__main__":
    app.run(debug=True)