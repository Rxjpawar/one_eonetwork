import json

with open("backup_data/eon_india_profiles.json", "r", encoding="utf-8") as file:
    url_data_india = json.load(file)

with open("backup_data/eon_usa_profiles.json", "r", encoding="utf-8") as file:
    url_data_usa = json.load(file)

with open("backup_data/eon_all_profiles.json", "r", encoding="utf-8") as file:
    url_data_all = json.load(file)

a = url_data_india["profiles"]
b = url_data_usa["profiles"]
c = url_data_all["profiles"]


india_usa_urls = set(p["url"] for p in a + b)

clean_profiles = [p for p in c if p["url"] not in india_usa_urls]

clean_data = {
    "total_profiles": len(clean_profiles),
    "profiles": clean_profiles
}

with open("backup_data/eon_clean_all_profiles.json", "w", encoding="utf-8") as file:
    json.dump(clean_data, file, ensure_ascii=False, indent=2)

print(f"India profiles:  {len(a)}")
print(f"USA profiles:    {len(b)}")
print(f"All profiles:    {len(c)}")
print(f"Clean profiles:  {len(clean_profiles)}")