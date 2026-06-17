import os
import json
from datetime import datetime
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from dotenv import load_dotenv

# Ensure environment is loaded
load_dotenv()

# Setup page
st.set_page_config(page_title="Yaad Say Kaam", layout="wide")

# Force LadyBug Theme CSS
st.markdown("""
<style>
    /* LadyBug Red & Black Theme */
    .stApp {
        background-color: #0f0f0f;
    }
    [data-testid="stSidebar"] {
        background-color: #1a0505;
        border-right: 2px solid #330000;
    }
    [data-testid="stSidebar"] * {
        color: #ffb3b3 !important;
    }
    h1, h2, h3, h4 {
        color: #ff3333 !important;
    }
    /* Animate Ladybug for alarms */
    @keyframes ladybug-bounce {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-10px) rotate(10deg); }
    }
    .alarm-bug {
        display: inline-block;
        font-size: 2.5em;
        animation: ladybug-bounce 0.5s infinite;
    }
</style>
""", unsafe_allow_html=True)

# Try to import agents
try:
    from agents.data_sentinel import process_message
    from agents.memory_agent import enrich_task
    from agents.privacy_auditor import audit_task
    from agents.reminder_agent import generate_reminder
    from agents.forgetting_agent import decide_forgetting
    from task_store import load_tasks, snooze_task, update_task_status, add_task, acknowledge_alarm
    from background_sync import start_background_sync
except ImportError as e:
    st.error(f"Failed to import modules: {e}")

try:
    from gmail_fetcher import fetch_unread_emails, mark_as_read
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

# Auto-refresh the page every 10 seconds to update the tasks dashboard and alarms
st_autorefresh(interval=10 * 1000, key="datarefresh")

@st.cache_resource
def init_background_thread():
    if GMAIL_AVAILABLE:
        start_background_sync(interval_seconds=15)
        return True
    return False

# Start the background sync only once
init_background_thread()

def init_session_state():
    if "processed" not in st.session_state:
        st.session_state.processed = False
    if "results" not in st.session_state:
        st.session_state.results = {}
    if "emails" not in st.session_state:
        st.session_state.emails = []
    if "raw_message" not in st.session_state:
        st.session_state.raw_message = ""

init_session_state()

# API Key Check
api_key = os.getenv("OPENAI_API_KEY")
groq_key = os.getenv("GROQ_API_KEY")

# Check st.secrets as fallback if running on Streamlit Cloud
try:
    if not api_key:
        api_key = st.secrets.get("OPENAI_API_KEY")
    if not groq_key:
        groq_key = st.secrets.get("GROQ_API_KEY")
except Exception:
    pass

if not api_key or not groq_key:
    st.sidebar.error("🔑 API Keys Required")
    if not api_key:
        api_key = st.sidebar.text_input("Enter your OpenAI API Key:", type="password")
        if api_key: os.environ["OPENAI_API_KEY"] = api_key
    if not groq_key:
        groq_key = st.sidebar.text_input("Enter your Groq API Key:", type="password")
        if groq_key: os.environ["GROQ_API_KEY"] = groq_key
        
    if not api_key or not groq_key:
        st.warning("Please enter your API Keys in the sidebar to unlock the app.")
        st.stop()
else:
    os.environ["OPENAI_API_KEY"] = api_key
    os.environ["GROQ_API_KEY"] = groq_key

st.sidebar.markdown("<h2 style='text-align: center; color: #ff3333 !important;'>🐞 LadyBugs Control Center</h2>", unsafe_allow_html=True)
st.sidebar.markdown("---")

creds_path = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')
token_path = os.path.join(os.path.dirname(__file__), '..', 'token.pickle')

has_creds = os.path.exists(creds_path)
has_token = os.path.exists(token_path)

if not GMAIL_AVAILABLE or not (has_creds and has_token):
    st.sidebar.warning("☁️ Cloud Mode: Gmail Fetcher is paused. Streamlit Cloud requires your local Google auth files.")
    
    cred_file = st.sidebar.file_uploader("Upload credentials.json", type=['json'])
    token_file = st.sidebar.file_uploader("Upload token.pickle", type=['pickle', 'pkl', ''])
    
    if cred_file and token_file:
        with open(creds_path, 'wb') as f:
            f.write(cred_file.getbuffer())
        with open(token_path, 'wb') as f:
            f.write(token_file.getbuffer())
        st.sidebar.success("✅ Auth files loaded! Refreshing...")
        st.rerun()

    input_source = st.sidebar.radio("🎯 Select Input Mode", ["Manual Input"])
else:
    input_source = st.sidebar.radio("🎯 Select Input Mode", ["Manual Input", "Fetch from Gmail"], index=0)

selected_email = None

if input_source == "Fetch from Gmail":
    if st.sidebar.button("📧 Fetch Unread Emails", use_container_width=True):
        with st.spinner("Fetching emails..."):
            try:
                emails = fetch_unread_emails()
                st.session_state.emails = emails
            except Exception as e:
                st.sidebar.error(f"Error fetching emails: {e}")
                
    if st.session_state.emails:
        email_options = {f"{e.get('subject')} - {e.get('sender')}": e for e in st.session_state.emails}
        selected_key = st.sidebar.selectbox("📬 Select an email to process", list(email_options.keys()))
        selected_email = email_options[selected_key]
    else:
        st.sidebar.info("No emails fetched yet. Click the button above!")

st.sidebar.markdown("---")
st.sidebar.caption("🔒 All data processed locally. No personal identifiers are stored.")

# Main Content
st.title("🐞 Yaad Say Kaam")
st.caption("A LadyBugs Team Project")
st.caption("Process any message without leaking personal data.")

if GMAIL_AVAILABLE:
    st.success("Background sync is running. Unread emails will be automatically converted to tasks every 15 seconds.")

tasks = load_tasks()

# Categorize tasks
active_tasks = []
missed_tasks = []
completed_tasks = []
now = datetime.now()

for t in tasks:
    if t.get('status') == 'completed':
        completed_tasks.append(t)
        continue
        
    deadline_str = t.get('deadline')
    is_missed = False
    if deadline_str:
        try:
            dt = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M:%S")
            if dt < now:
                is_missed = True
        except ValueError:
            pass
    
    if is_missed:
        missed_tasks.append(t)
    else:
        active_tasks.append(t)

# Global Alarms
alarms = []
non_completed = active_tasks + missed_tasks
for t in non_completed:
    alarm_time_str = t.get('next_alarm_time')
    if alarm_time_str:
        try:
            adt = datetime.strptime(alarm_time_str, "%Y-%m-%d %H:%M:%S")
            if adt <= now:
                alarms.append(t)
        except ValueError:
            pass
            
if alarms:
    st.markdown("<div class='alarm-bug'>🐞</div> <span style='color: #ff3333; font-size: 1.8em; font-weight: bold;'>WAKE UP! ACTIVE ALARM!</span>", unsafe_allow_html=True)
    for task in alarms:
        with st.container():
            st.error(f"**ALARM:** {task.get('abstract_reminder', 'N/A')} (Deadline: {task.get('deadline', 'N/A')})")
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("🔔 Snooze (15 Mins)", key=f"snooze_{task.get('task_id')}"):
                    snooze_task(task.get('task_id'), minutes=15)
                    st.rerun()
            with col2:
                if st.button("🤫 Dismiss Current Alarm", key=f"ack_{task.get('task_id')}"):
                    acknowledge_alarm(task.get('task_id'))
                    st.rerun()
            with col3:
                if st.button("✅ Mark as Done", key=f"done_{task.get('task_id')}"):
                    update_task_status(task.get('task_id'), 'completed')
                    st.rerun()
    st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📋 Active Tasks", "❌ Missed Tasks", "⚙️ Manual Processing"])

def sort_key(t, sort_by):
    if sort_by == "Created Time":
        return t.get("created_at") or ""
    elif sort_by == "Deadline":
        return t.get("deadline") or ""
    else:
        p_map = {"High": 1, "Medium": 2, "Low": 3}
        return p_map.get(t.get("priority") or "Low", 4)

def render_task_card(task, missed=False):
    forget = task.get("forget", False)
    if missed:
        bg_color = "#f8d7da"
        border_color = "#f5c6cb"
        text_color = "#721c24"
    else:
        bg_color = "#d4edda"
        border_color = "#c3e6cb"
        text_color = "#155724"
        
    st.markdown(f'''
    <div style="background-color: {bg_color}; border: 1px solid {border_color}; padding: 15px; border-radius: 5px; margin-bottom: 5px; color: {text_color};">
        <h4 style="margin-top: 0; color: {text_color};">Reminder: {task.get('abstract_reminder', 'N/A')}</h4>
        <strong>Action:</strong> {task.get('action', 'N/A')}<br>
        <strong>Deadline:</strong> {task.get('deadline', 'N/A')} | <strong>Status:</strong> {'MISSED' if missed else task.get('deadline_status', 'N/A')}<br>
        <strong>Priority:</strong> {task.get('priority', 'N/A')} | <strong>Category:</strong> {task.get('category', 'N/A')}<br>
        <strong>Created At:</strong> {task.get('created_at', 'N/A')}<br>
        <small>Next Alarm: {task.get('next_alarm_time', 'N/A')} | Acknowledged Alarms: {', '.join(task.get('acknowledged_alarms', []))}</small>
    </div>
    ''', unsafe_allow_html=True)
    
    if st.button("✅ Mark as Done", key=f"done_card_{task.get('task_id')}"):
        update_task_status(task.get('task_id'), 'completed')
        st.rerun()
    st.write("")

with tab1:
    st.header("Active Tasks")
    if not active_tasks:
        st.info("No active tasks right now.")
    else:
        sort_by_active = st.selectbox("Sort Active Tasks by", ["Deadline", "Created Time", "Priority"], key="sort_active")
        active_tasks = sorted(active_tasks, key=lambda t: sort_key(t, sort_by_active))
        
        for task in active_tasks:
            if task not in alarms:
                render_task_card(task, missed=False)
                
    if completed_tasks:
        with st.expander(f"📁 View Completed Tasks ({len(completed_tasks)})"):
            for task in reversed(completed_tasks):
                st.markdown(f'''
                <div style="background-color: #e2e3e5; border: 1px solid #d6d8db; padding: 15px; border-radius: 5px; margin-bottom: 10px; color: #383d41;">
                    <h4 style="margin-top: 0; color: #383d41;">✅ {task.get('abstract_reminder', 'N/A')}</h4>
                    <strong>Action:</strong> {task.get('action', 'N/A')} | <strong>Category:</strong> {task.get('category', 'N/A')}<br>
                    <strong>Completed At:</strong> {task.get('deadline', 'N/A')} (Deadline)
                </div>
                ''', unsafe_allow_html=True)

with tab2:
    st.header("Missed Tasks")
    if not missed_tasks:
        st.info("No missed tasks right now. Great job!")
    else:
        sort_by_missed = st.selectbox("Sort Missed Tasks by", ["Deadline", "Created Time", "Priority"], key="sort_missed")
        missed_tasks = sorted(missed_tasks, key=lambda t: sort_key(t, sort_by_missed))
        
        for task in missed_tasks:
            if task not in alarms:
                render_task_card(task, missed=True)

with tab3:
    st.header("Manual Processing")
    if not st.session_state.processed:
        raw_message_input = ""
        mark_read_opt = False
        
        if input_source == "Manual Input":
            raw_message_input = st.text_area("Enter a raw message", placeholder="e.g. Maryam, send the OS assignment tomorrow at 5 PM.")
        else:
            if selected_email:
                st.markdown(f"**Subject:** {selected_email.get('subject')}")
                st.markdown(f"**From:** {selected_email.get('sender')}")
                raw_message_input = f"Subject: {selected_email.get('subject')}\n\n{selected_email.get('body', '')}"
                st.text_area("Email Body (Read-Only)", value=raw_message_input, disabled=True, height=150)
                mark_read_opt = st.checkbox("Mark email as read after processing?")
            else:
                st.info("Please fetch and select an email from the sidebar.")

        col1, col2 = st.columns(2)
        with col1:
            task_status = st.selectbox("Task Status", ["pending", "completed"], index=0)
        with col2:
            created_at_input = st.text_input("Created At (YYYY-MM-DD HH:MM:SS)", value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
        if st.button("Process Message", type="primary", use_container_width=True):
            if not raw_message_input.strip():
                st.error("Message cannot be empty!")
                st.stop()
                
            st.session_state.raw_message = raw_message_input
            
            try:
                with st.spinner(" Data Sentinel extracting task info..."):
                    sentinel_result = process_message(raw_message_input)
                    
                with st.spinner(" Memory Agent enriching task..."):
                    memory_result = enrich_task(sentinel_result)
                    
                with st.spinner(" Privacy Auditor checking for leaks..."):
                    audited_result = audit_task(memory_result)
                    
                with st.spinner(" Reminder Agent generating abstract reminder..."):
                    reminder_result = generate_reminder(audited_result)
                    
                with st.spinner(" Forgetting Agent deciding if this should be forgotten..."):
                    reminder_result["status"] = task_status
                    reminder_result["created_at"] = created_at_input
                    forgetting_result = decide_forgetting(reminder_result)
                    
                st.session_state.results = {
                    "sentinel_result": sentinel_result,
                    "memory_result": memory_result,
                    "audited_result": audited_result,
                    "reminder_result": reminder_result,
                    "forgetting_result": forgetting_result
                }
                st.session_state.processed = True
                
                # Save manual task to task store so it appears in dashboard
                add_task(forgetting_result)
                
                if mark_read_opt and selected_email:
                    try:
                        mark_as_read(selected_email['id'])
                        st.success("Email marked as read.")
                    except Exception as e:
                        st.error(f"Failed to mark email as read: {e}")
                        
                st.rerun()
                
            except Exception as e:
                st.error(f"Pipeline failed: {e}")

    else:
        # Display Results
        results = st.session_state.results
        sentinel_result = results.get("sentinel_result", {})
        memory_result = results.get("memory_result", {})
        audited_result = results.get("audited_result", {})
        reminder_result = results.get("reminder_result", {})
        forgetting_result = results.get("forgetting_result", {})
        
        st.success(f"**Task Summary:** {sentinel_result.get('summary')}\n\n🟢 **Raw message discarded – no personal data stored**")
        
        st.info(f"**Action:** {memory_result.get('action')}\n\n**Deadline:** {memory_result.get('deadline')}\n\n**Priority:** {memory_result.get('priority')}\n\n**Category:** {memory_result.get('category')}")
        
        if audited_result.get("has_personal_data"):
            st.warning(f"**Privacy Alert!** {audited_result.get('alert_message')}\n\n**Risk:** {audited_result.get('risk_level')}\n\n**Entities:** {', '.join(audited_result.get('detected_entities', []))}")
        else:
            st.success("✅ No personal data detected – privacy check passed")
            
        st.info(f"**Abstract Reminder:** {reminder_result.get('abstract_reminder')}\n\n**Urgency:** {reminder_result.get('urgency')}")
        
        forget = forgetting_result.get("forget")
        reason = forgetting_result.get("reason")
        decision_text = "Yes" if forget else "No"
        st.info(f"**Forget Task?** {decision_text}\n\n**Reason:** {reason}")
        
        # Expanders
        with st.expander("📄 Full Data Sentinel output"):
            st.json(sentinel_result)
        with st.expander("📄 Full Memory Agent output"):
            st.json(memory_result)
        with st.expander("📄 Full Privacy Auditor output"):
            st.json(audited_result)
        with st.expander("📄 Full Reminder Agent output"):
            st.json(reminder_result)
        with st.expander("📄 Full Forgetting Agent output"):
            st.json(forgetting_result)
            
        if st.button("🔄 Start Over", type="secondary", use_container_width=True):
            st.session_state.processed = False
            st.session_state.results = {}
            st.session_state.raw_message = ""
            st.rerun()
