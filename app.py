from flask import Flask, request, jsonify, render_template, redirect, url_for, Response, stream_with_context
from tasks import sub_srt, celery   # ✅ 这里引入同一个 celery 实例
import time,json
import  os
app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # 确保目录存在
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# @app.route('/upload', methods=['GET', 'POST'])
# def upload_file():
#     if request.method == 'GET':
#         # 返回表单页面
#         return render_template('upload.html')
#     if 'file' not in request.files:
#         return "没有文件 part"
#
#     file = request.files['file']
#     if file.filename == '':
#         return "没有选择文件"
#
#     # 保存到 uploads 文件夹
#
#
#     return render_template("upload_success.html", filename=file.filename)

@app.route("/", methods=["GET", "POST"])
def start_task():
    if request.method == "POST":
        file = request.files['file']
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(save_path)
        time.sleep(2)
        task = sub_srt.delay()
        return redirect(url_for('task_status_page', task_id=task.id))
    return render_template("count.html")

@app.route("/stream/<task_id>")
def stream(task_id):
    def event_stream(task_id):
        while True:
            task = celery.AsyncResult(task_id)
            if task.state == 'PENDING':
                yield f"data: {json.dumps({'state': task.state, 'current': 0, 'total': 0})}\n\n"
            elif task.state == 'PROGRESS':
                yield f"data: {json.dumps({'state': task.state, 'current': task.info.get('current', 0), 'total': task.info.get('total', 1)})}\n\n"
            elif task.state == 'SUCCESS':
                yield f"data: {json.dumps({'state': task.state, 'current': task.result.get('total', 0), 'total': task.result.get('total', 0), 'result': task.result.get('result', '')})}\n\n"
                break
            else:
                yield f"data: {json.dumps({'state': task.state})}\n\n"
                break
            time.sleep(0.5)
            print(task.state)
    return Response(stream_with_context(event_stream(task_id)), mimetype="text/event-stream")

@app.route("/task_status_page/<task_id>")
def task_status_page(task_id):
    return render_template("state.html", task_id=task_id)

if __name__ == "__main__":
    app.run(debug=True)
