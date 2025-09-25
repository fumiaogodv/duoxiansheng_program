from celery import Celery

celery = Celery('tasks', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

@celery.task
def long_task(x, y):
    import time
    time.sleep(5)
    return x + y
