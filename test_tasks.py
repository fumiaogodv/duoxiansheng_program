from celery import Celery
import time

celery = Celery('tasks', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

@celery.task(bind=True)
def do_work(self):
    final_num=100
    for num in range(1,final_num):
        time.sleep(0.1)
        self.update_state(
            state='PROGRESS',
            meta={'current':num,'total':final_num}
        )

    return {'current':final_num,'total':final_num,'result':final_num}