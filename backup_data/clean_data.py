import json
with open("backup_data/eon_india_profiles.json", "r", encoding="utf-8") as file:
    url_data_india = json.load(file)

print(len(url_data_india["profiles"]))