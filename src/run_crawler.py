from .crawler import run_crawl
import json
if __name__=="__main__":
    print(json.dumps(run_crawl(),indent=2))
