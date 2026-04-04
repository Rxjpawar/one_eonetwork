from httpx import URL
from app.workflow import pipeline_flow
import os
from dotenv import load_dotenv
load_dotenv()

EXEL_FILE=os.getenv("EXEL_FILE")
URLS_FILE=os.getenv("URLS_FILE")
FAILED_URLS_FILE=os.getenv("FAILED_URLS_FILE")

def run():
    print("---------- Running the pipeline ----------")
    pipeline_flow(EXEL_FILE,URLS_FILE,FAILED_URLS_FILE)
    print('---------- Pipeline ran successfully ----------')

if __name__ == "__main__":
    run()