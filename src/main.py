import os
import json
from datetime import datetime
from dotenv import load_dotenv

# 1. Load OPENAI_API_KEY from .env
load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    raise EnvironmentError("ERROR: OPENAI_API_KEY missing from environment variables.")

# 2. Import agent functions
from agents.data_sentinel import process_message
from agents.memory_agent import enrich_task
from agents.privacy_auditor import audit_task
from agents.reminder_agent import generate_reminder
from agents.forgetting_agent import decide_forgetting

# 3. Optional import from gmail_fetcher
try:
    from gmail_fetcher import fetch_unread_emails
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

def run_pipeline(raw_message: str, status: str = "pending", created_at: str = None) -> dict:
    """
    Executes the full pipeline sequentially for a given raw message.
    """
    try:
        if not created_at:
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        print("\n--- Pipeline Step 1: Data Sentinel ---")
        sentinel_result = process_message(raw_message)
        
        print("\n--- Pipeline Step 2: Memory Agent ---")
        memory_result = enrich_task(sentinel_result)
        
        print("\n--- Pipeline Step 3: Privacy Auditor ---")
        audited_result = audit_task(memory_result)
        
        print("\n--- Pipeline Step 4: Reminder Agent ---")
        reminder_result = generate_reminder(audited_result)
        
        print("\n--- Pipeline Step 5: Forgetting Agent ---")
        # Ensure status and created_at are present for forgetting logic
        reminder_result["status"] = status
        reminder_result["created_at"] = created_at
        forgetting_result = decide_forgetting(reminder_result)
        
        return {
            "sentinel_result": sentinel_result,
            "memory_result": memory_result,
            "audited_result": audited_result,
            "reminder_result": reminder_result,
            "forgetting_result": forgetting_result
        }
    except Exception as e:
        raise Exception(f"Pipeline failed at an intermediate step: {e}")

if __name__ == "__main__":
    try:
        print("🚀 Privacy Memory Guardian Pipeline")
        
        mode = os.getenv("PIPELINE_MODE")
        if not mode:
            mode = input("Select mode ('test' or 'gmail') [default: test]: ").strip().lower()
            if not mode:
                mode = "test"
                
        if mode == "test":
            print("\n[Running in TEST mode]")
            raw_message = "Maryam, send the OS assignment tomorrow."
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            results = run_pipeline(raw_message, status="pending", created_at=created_at)
            
            print("\n=== Final Pipeline Results ===")
            print(json.dumps(results["forgetting_result"], indent=2))
            
        elif mode == "gmail":
            print("\n[Running in GMAIL mode]")
            if not GMAIL_AVAILABLE:
                print("Gmail fetcher not available. Please install google-api-python-client and google-auth-oauthlib, and place credentials.json in the project root.")
                exit(1)
            
            emails = fetch_unread_emails()
            if not emails:
                print("No unread emails found.")
            else:
                for idx, email in enumerate(emails, start=1):
                    print(f"\n=========================================")
                    print(f"Processing Email {idx}/{len(emails)}")
                    print(f"Subject: {email.get('subject')}")
                    print(f"From: {email.get('sender')}")
                    print(f"Date: {email.get('date')}")
                    print(f"=========================================")
                    
                    raw_message = f"Subject: {email.get('subject')}\nBody: {email.get('body')}"
                    
                    # Extract date or fallback to today
                    # Email dates are complex, fallback to now for simplicity in YYYY-MM-DD HH:MM:SS
                    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    try:
                        results = run_pipeline(raw_message, status="pending", created_at=created_at)
                        print("\n=== Final Pipeline Results for Email ===")
                        print(json.dumps(results["forgetting_result"], indent=2))
                    except Exception as e:
                        print(f"Failed to process email {email.get('id')}: {e}")
        else:
            print(f"Unknown mode: '{mode}'. Please use 'test' or 'gmail'.")
            
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
    finally:
        print("\nPipeline complete.")
