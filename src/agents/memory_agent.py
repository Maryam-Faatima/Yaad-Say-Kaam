import os
import json
from dotenv import load_dotenv
from openai import OpenAI
import openai
from groq import Groq

def enrich_task(task_data: dict) -> dict:
    """
    Takes an extracted task from data_sentinel and uses OpenAI to generate 
    a neutral reminder and infer a category, merging them into the original task_data.
    """
    load_dotenv()
    
    client = OpenAI()
    
    system_prompt = (
        "You are Memory Agent, an abstract memory processor that normally never stores personal details.\n"
        "Given the extracted task data, generate a short, neutral reminder.\n"
        "IMPORTANT: You MAY include the first name of a contact (e.g., 'Zoe') if it is present in the action so the user knows who to contact. DO NOT include other identifiable info like phone numbers or emails.\n"
        "The reminder should be a single sentence that says what needs to be done and by when, "
        "using only the provided fields.\n"
        "Also infer a category for this task: one of 'Work', 'Personal', 'Study', 'Health', 'Misc'.\n"
        "Return ONLY a raw JSON object with these exact keys: reminder (string), category (string). "
        "No markdown, no explanation."
    )
    
    user_message = json.dumps(task_data)
    
    try:
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
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
                    {"role": "user", "content": user_message}
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
        
        # Merge original task data with the new generated fields
        enriched_data = task_data.copy()
        enriched_data["reminder"] = extracted_data.get("reminder")
        enriched_data["category"] = extracted_data.get("category")
        
        print(f"Memory Agent enriched task: {task_data.get('summary')}")
        return enriched_data
        
    except json.JSONDecodeError:
        raise ValueError(f"Failed to parse JSON. Raw response: {raw_response}")
    except Exception as e:
        raise ValueError(f"An error occurred: {e}")
