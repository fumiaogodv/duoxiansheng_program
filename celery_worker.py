from app import celery  # 导入 app.py 中的 celery 实例

# 启动 worker
# 在命令行执行： celery -A celery_worker.celery worker --loglevel=info
