from flask import Flask, request, jsonify, render_template, redirect, url_for
from tasks import sub_srt

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def start_task():
    if request.method == "POST":
        # 如果不需要 x，可以直接启动任务
        task = sub_srt.delay()
        return redirect(url_for('task_status_page', task_id=task.id))
    return render_template("count.html")

@app.route("/task_status/<task_id>")
def task_status(task_id):
    task = sub_srt.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {'state': task.state, 'current': 0, 'total': 0}
    elif task.state == 'PROGRESS':
        response = {
            'state': task.state,
            'current': task.info.get('current', 0),
            'total': task.info.get('total', 1)
        }
    elif task.state == 'SUCCESS':
        response = {
            'state': task.state,
            'current': task.result.get('current'),
            'total': task.result.get('total'),
            'result': task.result.get('result')
        }
    else:
        response = {'state': task.state}
    return jsonify(response)

@app.route("/task_status_page/<task_id>")
def task_status_page(task_id):
    return render_template("state.html", task_id=task_id)

if __name__ == "__main__":
    app.run(debug=True)
