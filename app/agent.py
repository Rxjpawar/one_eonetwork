import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

def ai_agent(context):

    client = OpenAI(api_key=os.getenv("GROQ_API_KEY"),base_url="https://api.groq.com/openai/v1")

    SYSTEM_PROMPT = fr'''
    You are agent who format the provided {context} data in give example
    and generate a summary based on the given data
    Example :
    ---------------------------------------------------------------
        Personal Information
        Name: Abhay Surendra Mehta
        Gender: Male
        Location: Chennai, India
        Membership Type: Member
        Member Since: 09-Dec-2002
        Primary Chapter: EO Chennai
        
        Professional Experience
        Trustee – Mehta Jewellery
        Location: Chennai, India
        Duration: Sep 1992 – Present (33+ years)
        Industry: Retail Jewellery & Manufacturing
        Qualifying Company: Yes

        Contact Information
        Emails
        abhaysmehta@gmail.com
        Phone Numbers
        Preferred: +91 44 24662665
        Mobile: +91 9884266649

        Addresses
        
        Primary Address
        4AB, Anakara, 13 Gilchrist Ave.,
        Harrington Road, Chennai, Tamil Nadu, India – 600031

        Secondary Address
        No. 43, C.P. Ramaswamy Road,
        Abhiramapuram, Chennai, Tamil Nadu, India – 600018

        Family Information
        Spouse
        Name: Niyati Mehta
        Email: Niyatiamehta@gmail.com
        
        Child
        Name: Dhruv Mehta
        Email: dhtuvmehta4good@gmail.com
        DOB: 31st March
   
        Summary (Quick View)
        Veteran entrepreneur with 30+ years in jewellery business
        Long-standing EO member (since 2002)
        Held both global & local leadership roles
        Diverse interests across culture, sports, and business sectors

        ---------------------------------------------------------------
        strictly follow the json schema for data output :
        {{
        "personal_information": "Name: Abhay Surendra Mehta\nGender: Male\nLocation: Chennai, India\nMembership Type: Member\nMember Since: 09-Dec-2002\nPrimary Chapter: EO Chennai",

        "professional_experience": "Designation: Trustee – Mehta Jewellery\nLocation: Chennai, India\nDuration: Sep 1992 – Present (33+ years)\nIndustry: Retail Jewellery & Manufacturing\nQualifying Company: Yes",

        "contact_information": "Email:\n- abhaysmehta@gmail.com\n\nPhone Numbers:\n- Preferred: +91 44 24662665\n- Mobile: +91 9884266649\n\nAddresses:\nPrimary Address:\n4AB, Anakara, 13 Gilchrist Ave.,\nHarrington Road, Chennai, Tamil Nadu, India – 600031\n\nSecondary Address:\nNo. 43, C.P. Ramaswamy Road,\nAbhiramapuram, Chennai, Tamil Nadu, India – 600018",

        "family_information": "Spouse:\n- Name: Niyati Mehta\n- Email: Niyatiamehta@gmail.com\n- Access: Granted\n\nChild:\n- Name: Dhruv Mehta\n- Email: dhtuvmehta4good@gmail.com\n- DOB: 31st March\n- Access: Granted",

        "summary": Summary:\n "Veteran entrepreneur with 30+ years in jewellery business\nLong-standing EO member since 2002\nHeld both global and local leadership roles\nDiverse interests across culture, sports, and business sectors"
        }}
        ---------------------------------------------------------------
    '''  

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role":"user","content":SYSTEM_PROMPT}],
        response_format={"type":"json_object"},
    )
    output = response.choices[0].message.content
    return output

# ai=ai_agent(profile_text_data)
# llm_data = json.loads(ai)
# print(ai)

# {
# "personal_information": "Name: John Doe\nGender: Male\nLocation: New York, USA\nMembership Type: Member\nMember Since: 
# 01-Jan-2010\nPrimary Chapter: EO New York",
#   "professional_experience": "Designation: CEO – XYZ Corporation\nLocation: New York, USA\nDuration: Jan 2005 – Present (18+ years)\nIndustry: Technology\nQualifying Company: Yes",
#   "contact_information": "Email:\n- johndoe@example.com\n\nPhone Numbers:\n- Preferred: +1 212 1234567\n- Mobile: +1 917 8765432\n\nAddresses:\nPrimary Address:\n123 Main St, New York, NY 10001\n\nSecondary Address:\n456 Park Ave, New York, NY 10022",
#   "family_information": "Spouse:\n- Name: Jane Doe\n- Email: janedoe@example.com\n- Access: Granted\n\nChild:\n- Name: 
# Emily Doe\n- Email: emilydoe@example.com\n- DOB: 12th June\n- Access: Granted",
#   "summary": "Seasoned entrepreneur with 20+ years in technology industry\nLong-standing EO member since 2010\nHeld both global and local leadership roles\nDiverse interests across culture, sports, and business sectors"
# }

# print(llm_data["personal_information"])
# print(llm_data["professional_experience"])
# print(llm_data["contact_information"])
# print(llm_data["family_information"])
# print(llm_data["summary"])