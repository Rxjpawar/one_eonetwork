from app.workflow import pipeline_flow
FILE_PATH = "data/eon_india_profiles.xlsx"

def run():
    print("---------- Running the pipeline ----------")
    pipeline_flow(FILE_PATH)
    print('---------- Pipeline ran successfully ----------')

if __name__ == "__main__":
    run()