import datetime
import time

import pytz
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from database_classes import Pool


async def schedule_start_pool(pool: Pool, callback_send_message):
    now = datetime.datetime.utcnow()
    if not pool.start_date:
        raise ValueError("Ошибка даты окончания опроса.")
    if pool.start_date < now < pool.end_date:
        # отправляем немедленно
        await callback_send_message(pool.id)
        return
    job_name = f"start_{pool.id}_{pool.pool_channel_id}_{pool.pool_message_id}"
    scheduler.add_job(callback_send_message,
                      trigger="date",
                      args=[pool.id],
                      id=job_name,
                      name=job_name,
                      replace_existing=True,
                      run_date=pool.start_date)


def schedule_end_pool(pool: Pool, callback_send_message):
    if not pool.end_date:
        raise ValueError("Дата завершения опроса не установлена!")
    if pool.end_date < datetime.datetime.utcnow():
        raise ValueError("Дата завершения опроса уже прошла, опрос не был отправлен.")

    job_name = f"end_{pool.id}_{pool.pool_channel_id}_{pool.pool_message_id}"
    scheduler.add_job(callback_send_message,
                      args=[pool.id],
                      trigger="date",
                      id=job_name,
                      name=job_name,
                      replace_existing=True,
                      run_date=pool.end_date)



executor = AsyncIOExecutor()
scheduler = AsyncIOScheduler(timezone=pytz.utc, executors={"default": executor})
scheduler.add_jobstore(SQLAlchemyJobStore(url='sqlite:///data/jobs.db'))
scheduler._job_defaults["misfire_grace_time"] = 7 * 24 * 60 * 60

# scheduler_async.add_job(print_time, 'interval', seconds=1)
scheduler.start()


