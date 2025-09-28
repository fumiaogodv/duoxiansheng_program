# tasks.py
from celery import Celery
import time
import pysrt

celery = Celery('tasks', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

@celery.task(bind=True)
def sub_srt(self):
    subs = pysrt.open("one.srt")
    srt_num = len(subs)
    for i in subs:
        if i.text.strip():
            words = i.text.strip().split()
            first_word = words[0]
            time.sleep(0.2)
        self.update_state(
            state='PROGRESS',
            meta={'current': i.index, 'total': srt_num}
        )
    return {'current': srt_num, 'total': srt_num, 'result': srt_num}
