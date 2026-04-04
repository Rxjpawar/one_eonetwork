import os
import json
from app.agent import ai_agent
from app.get_data import fetch_profile_text
from app.save_to_exel import save_to_excel
from dotenv import load_dotenv
load_dotenv()


def pipeline_flow(EXEL_FILE,URLS_FILE,FAILED_URLS_FILE):

    with open(f"urls/{URLS_FILE}.json", "r", encoding="utf-8") as file:
        url_data = json.load(file)

    total = len(url_data["profiles"])
    print(f"[*] Total profiles to process: {total}")

    failed = []

    for index in range(total):
        profile     = url_data["profiles"][index]
        profile_name = profile.get("name", "Unknown")
        profile_url  = profile.get("url", "")
        count        = index + 1

        print(f"\n---------- [{count}/{total}] {profile_name} ----------")

        try:
            # 1. Fetch raw profile text from EON
            profile_text_data = fetch_profile_text(profile_url)

            if not profile_text_data or not profile_text_data.strip():
                print(f"  [SKIP] Empty profile text for {profile_name}")
                failed.append({"index": index, "name": profile_name, "url": profile_url, "reason": "empty profile text"})
                continue

            # 2. Run LLM agent
            ai_response = ai_agent(profile_text_data)

            # 3. Parse JSON — catch malformed LLM output
            try:
                llm_data = json.loads(ai_response)
            except json.JSONDecodeError as je:
                print(f"  [SKIP] JSON parse error for {profile_name}: {je}")
                failed.append({"index": index, "name": profile_name, "url": profile_url, "reason": f"JSON error: {je}"})
                continue

            # 4. Build row — use .get() so missing keys don't crash
            row = {
                "personal_information":   llm_data.get("personal_information", "Not Found"),
                "professional_experience": llm_data.get("professional_experience", "Not Found"),
                "contact_information":    llm_data.get("contact_information", "Not Found"),
                "family_information":     llm_data.get("family_information", "Not Found"),
                "summary":                llm_data.get("summary", "Not Found"),
            }

            # 5. Save to Excel
            save_to_excel([row], EXEL_FILE)
            print(f"  [OK] Saved: {profile_name}")

        except Exception as e:
            print(f"  [ERROR] {profile_name}: {e}")
            failed.append({"index": index, "name": profile_name, "url": profile_url, "reason": str(e)})
            continue

    # Save failed profiles list for retry
    if failed:
        with open(f"ulrs_but_failed/{FAILED_URLS_FILE}.json", "w", encoding="utf-8") as f:
            json.dump(failed, f, indent=2, ensure_ascii=False)
        print(f"\n[!] {len(failed)} profiles failed. See failed_profiles.json")

    print(f"\n[+] Pipeline complete. Processed {total - len(failed)}/{total} profiles.")