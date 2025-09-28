from celery import Celery
import time

celery = Celery('tasks', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

@celery.task(bind=True)
def long_task(self, x):
    y = 0
    while y < x:
        y += 1
        time.sleep(0.1)  # 模拟耗时

        # 每次循环更新任务状态，meta里保存y的值
        self.update_state(
            state='PROGRESS',
            meta={'current': y, 'total': x}
        )

    # 返回最终结果
    return {'current': y, 'total': x, 'result': y}
