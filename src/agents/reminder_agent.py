import os
import json
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
import openai
from groq import Groq

def generate_reminder(task_data: dict) -> dict:
    """
    Takes an audited task dictionary, calculates the deadline status, 
    and uses OpenAI to generate an abstract reminder and urgency level.
    """
    load_dotenv()
    
    deadline_str = task_data.get('deadline') or ""
    
    try:
        deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M:%S").date()
    except ValueError:
        try:
            deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
        except ValueError:
            deadline_date = datetime.now().date()
            
    today = datetime.now().date()
    days_until = (deadline_date - today).days
    
    if days_until < 0:
        deadline_status = "exceeded"
    elif 0 <= days_until <= 3:
        deadline_status = "approaching"
    else:
        deadline_status = "on_track"
        
    client = OpenAI()
    
    system_prompt = (
        "You are Reminder Agent, a minimalist task reminder system.\n"
        "Given the task details, generate a short, abstract reminder that focuses on the action and deadline status.\n"
        "IMPORTANT: You may include the first name of the contact (if present in the action) so the user knows who the task involves (e.g., 'Call Zoe'). Do NOT include any other personal identifiers like phone numbers or emails.\n"
        "Use the action, deadline status, priority, and category to craft a concise reminder like: 'Call Zoe – deadline exceeded' or 'Submit report – approaching deadline'.\n"
        "Also assign an urgency level: one of 'now' (if deadline_status is 'exceeded'), 'soon' (if 'approaching'), or 'later' (if 'on_track').\n"
        "Return ONLY a raw JSON object with these exact keys: abstract_reminder (string), urgency (string). No markdown, no explanation."
    )
    
    user_message = (
        f"action: {task_data.get('action')}\n"
        f"deadline: {deadline_str}\n"
        f"deadline_status: {deadline_status}\n"
        f"priority: {task_data.get('priority')}\n"
        f"category: {task_data.get('category')}"
    )
    
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
        
        # Build the final dict merging original data and new properties
        final_dict = task_data.copy()
        final_dict["deadline_status"] = deadline_status
        final_dict["abstract_reminder"] = extracted_data.get("abstract_reminder")
        final_dict["urgency"] = extracted_data.get("urgency")
        
        print(f"Reminder generated: {final_dict['abstract_reminder']}")
        return final_dict
        
    except json.JSONDecodeError:
        raise ValueError(f"Failed to parse JSON. Raw response: {raw_response}")
    except Exception as e:
        raise ValueError(f"An error occurred: {e}")
