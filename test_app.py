from flask import Flask, request, jsonify, render_template, redirect, url_for, Response, stream_with_context
from test_tasks import do_work,celery
import time
app=Flask(__name__)

@app.route("/",methods=["GET","POST"])
def start_task():
    if request.method == "POST":
        task = do_work.delay()
        return redirect(url_for('task_status_page', task_id=task.id))
    return render_template("count.html")

@app.route("/stream/<task_id>")
def stream(task_id):
    def event_stream(task_id):
        while True:
            task = celery.AsyncResult(task_id)  # ✅ 用 tasks.py 的 celery
            if task.state == 'PENDING':
                yield f"data: {{\"state\": \"{task.state}\", \"current\": 0, \"total\": 0}}\n\n"
            elif task.state == 'PROGRESS':
                yield f"data: {{\"state\": \"{task.state}\", \"current\": {task.info.get('current',0)}, \"total\": {task.info.get('total',1)}}}\n\n"
            elif task.state == 'SUCCESS':
                yield f"data: {{\"state\": \"{task.state}\", \"current\": {task.result.get('current')}, \"total\": {task.result.get('total')}, \"result\": {task.result.get('result')}}}\n\n"
                break
            else:
                yield f"data: {{\"state\": \"{task.state}\"}}\n\n"
                break
            time.sleep(1)
            print("当前状态:", task.state)
    return Response(stream_with_context(event_stream(task_id)), mimetype="text/event-stream")

@app.route("/task_status_page/<task_id>")
def task_status_page(task_id):
    return render_template("test_state.html", task_id=task_id)

if __name__ == "__main__":
    app.run(debug=True)

