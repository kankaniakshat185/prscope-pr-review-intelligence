import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv('.env')
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

try:
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
    response = model.generate_content('hello')
    print("lite SUCCESS:", response.text)
except Exception as e:
    print("lite ERROR:", e)
