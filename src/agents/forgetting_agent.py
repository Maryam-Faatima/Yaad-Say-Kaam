import os
import json
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
import openai
from groq import Groq

def decide_forgetting(task_data: dict) -> dict:
    """
    Decides whether a task should be forgotten (deleted) based on a rule-based
    pre-check or an OpenAI evaluation of the abstract task data.
    """
    load_dotenv()
    
    today = datetime.now().date()
    
    # Resolve optional keys or apply defaults
    status = task_data.get("status") or "pending"
    deadline_str = task_data.get("deadline") or ""
    
    created_at_str = task_data.get("created_at") or ""
    if not created_at_str:
        created_at_str = deadline_str if deadline_str else today.strftime("%Y-%m-%d %H:%M:%S")
        
    def parse_date(date_str):
        try:
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").date()
        except ValueError:
            try:
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return today

    created_at_date = parse_date(created_at_str)
    deadline_date = parse_date(deadline_str)
        
    deadline_status = task_data.get("deadline_status", "")
    priority = task_data.get("priority", "")
    
    forget = None
    reason = ""
    
    # Rule-based Pre-checks
    # 1. Completed and older than 30 days
    if status.lower() == "completed":
        age = (today - created_at_date).days
        if age > 30:
            forget = True
            reason = "Completed and older than 30 days"
            
    # 2. Exceeded by > 7 days and Low priority
    if forget is None and deadline_status == "exceeded" and priority.lower() == "low":
        days_exceeded = (today - deadline_date).days
        if days_exceeded > 7:
            forget = True
            reason = "Deadline exceeded for more than 7 days with low priority"
            
    # If a rule triggered, return immediately without API call
    if forget is not None:
        final_dict = task_data.copy()
        final_dict["forget"] = forget
        final_dict["reason"] = reason
        print(f"Forgetting decision made for task {final_dict.get('task_id')}: forget={forget}")
        return final_dict
        
    # Otherwise, fallback to OpenAI LLM evaluation
    client = OpenAI()
    
    system_prompt = (
        "You are Forgetting Agent, responsible for deleting irrelevant memories. "
        "Given the abstract task data (which contains no personal identifiers), "
        "decide if this task should be forgotten (deleted) because it is no longer relevant, "
        "already completed, or expired. Consider the deadline, priority, urgency, and any status "
        "if provided. If the task is completed and more than 30 days old, or if the deadline "
        "has been exceeded for more than 7 days and priority is low, you may suggest forgetting. "
        "But also consider if the task might still be relevant (e.g., a recurring reminder). "
        "Return ONLY a raw JSON object with these exact keys: forget (boolean), reason (string explaining why). "
        "No markdown, no explanation."
    )
    
    user_message = (
        f"action: {task_data.get('action')}\n"
        f"deadline: {deadline_str}\n"
        f"priority: {priority}\n"
        f"category: {task_data.get('category')}\n"
        f"abstract_reminder: {task_data.get('abstract_reminder')}\n"
        f"urgency: {task_data.get('urgency')}\n"
        f"deadline_status: {deadline_status}\n"
        f"status: {status}\n"
        f"created_at: {created_at_str}"
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
        
        # Build the final dict
        final_dict = task_data.copy()
        final_dict["forget"] = extracted_data.get("forget", False)
        final_dict["reason"] = extracted_data.get("reason", "")
        
        print(f"Forgetting decision made for task {final_dict.get('task_id')}: forget={final_dict['forget']}")
        return final_dict
        
    except json.JSONDecodeError:
        raise ValueError(f"Failed to parse JSON. Raw response: {raw_response}")
    except Exception as e:
        raise ValueError(f"An error occurred: {e}")
