from apscheduler.schedulers.blocking import BlockingScheduler
from src.crawler import run_crawl

if __name__=="__main__":
    scheduler=BlockingScheduler()
    scheduler.add_job(run_crawl,"interval",hours=24,id="daily_scholarship_crawl",max_instances=1,coalesce=True)
    print("Daily crawler started. First crawl begins now.")
    run_crawl()
    scheduler.start()
