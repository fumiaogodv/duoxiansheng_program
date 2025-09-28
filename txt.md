redis-server
python app.py
celery -A tasks.celery worker --loglevel=info
curl -X POST -F "x=5" -F "y=10" http://127.0.0.1:5000/start_task

ps aux | grep 'celery'
kill -9 <PID>

ps aux | grep redis
kill -9 <PID>



It realizes the continuous transmission of the results of 
the function during its operation, and then displays the results.
