# test_tasks.py
from celery import Celery
import subprocess
import time
import re
import os

celery = Celery(
    'tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

@celery.task(bind=True)
def sub_srt(self):
    import os, re, subprocess, time

    log_file = "main.log"
    cmd = "nohup python3 main.py > main.log 2>&1 &"

    subprocess.Popen(cmd, shell=True)

    while not os.path.exists(log_file):
        time.sleep(0.5)

    current, total = 0, 0
    last_current = -1

    while True:
        try:
            with open(log_file, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                read_size = min(4096, size)
                f.seek(-read_size, 2)
                lines = f.read().decode(errors="ignore").splitlines()

            finished = False

            for line in reversed(lines):
                # ✅ 检测进度
                match = re.search(r"正在翻译段落\s+(\d+)\s*/\s*(\d+)", line)
                if match:
                    current = int(match.group(1))
                    total = int(match.group(2))
                    break

                # ✅ 检测结束关键词
                if "翻译完成" in line or "成功将双语字幕保存到" in line:
                    finished = True

            # ✅ 只有进度变动时才更新，减少压力
            if current != last_current:
                self.update_state(
                    state='PROGRESS',
                    meta={'current': current, 'total': total}
                )
                last_current = current

            # ✅ 翻译完成 → 强制最后一次推送 100%
            if finished or (total > 0 and current >= total):
                self.update_state(
                    state='PROGRESS',
                    meta={'current': total, 'total': total}
                )
                break

            time.sleep(0.3)

        except Exception as e:
            print(f"[日志监控异常] {e}")
            time.sleep(1)

    # ✅ 返回最终状态（让 Celery 状态变为 SUCCESS）
    return {'current': total, 'total': total, 'result': '翻译完成'}
