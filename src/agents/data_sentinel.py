import os
import json
import uuid
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
import openai
from groq import Groq

def process_message(raw_message: str) -> dict:
    """
    Processes a raw user message using OpenAI to extract action, deadline, priority, and a neutral summary.
    Generates a unique task_id and returns a dictionary with the extracted data.
    """
    load_dotenv()
    
    client = OpenAI()
    task_id = str(uuid.uuid4())
    today_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    system_prompt = (
        "You are Data Sentinel, an extractor that never stores or shares raw text. \n"
        "From the user message, extract only:\n"
        "- action: a short verb phrase describing what needs to be done. IMPORTANT: Include the first name of the contact/target if necessary for context (e.g., 'Call Zoe').\n"
        f"- deadline: a date and time string (if relative, convert to 'YYYY-MM-DD HH:MM:SS' based on now: {today_datetime}. If no time is specified, use '23:59:59')\n"
        "- priority: one of 'High', 'Medium', 'Low' (infer from urgency words)\n"
        "- summary: a 1-sentence neutral description\n"
        "Return ONLY a raw JSON object with these exact keys: action, deadline, priority, summary. No markdown, no explanation."
    )
    
    try:
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": raw_message}
                ],
                temperature=0.0
            )
        except (openai.RateLimitError, openai.AuthenticationError):
            print("OpenAI quota exceeded or auth failed, falling back to Groq...")
            groq_client = Groq()
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": raw_message}
                ],
                temperature=0.0
            )
        
        raw_response = response.choices[0].message.content.strip()
        
        # Strip markdown block formatting if present
        cleaned_response = raw_response
        if cleaned_response.startswith("```"):
            cleaned_response = cleaned_response.strip("`").strip()
            if cleaned_response.lower().startswith("json"):
                cleaned_response = cleaned_response[4:].strip()
                
        extracted_data = json.loads(cleaned_response)
        
        final_dict = {
            "task_id": task_id,
            "action": extracted_data.get("action"),
            "deadline": extracted_data.get("deadline"),
            "priority": extracted_data.get("priority"),
            "summary": extracted_data.get("summary")
        }
        
        print(f"Data Sentinel processed: {final_dict['summary']}")
        return final_dict
        
    except json.JSONDecodeError:
        raise ValueError(f"Failed to parse JSON. Raw response: {raw_response}")
    except Exception as e:
        raise ValueError(f"An error occurred: {e}")
