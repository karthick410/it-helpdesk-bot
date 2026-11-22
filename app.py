import csv
import io
from datetime import datetime
import streamlit as st
from google import genai
from pypdf import PdfReader

st.set_page_config(page_title="IT Helpdesk Bot", page_icon="🤖", layout="centered")

st.title("🤖 IT Helpdesk Bot")
st.write("Ask your IT questions or upload your company IT manual PDFs for instant help!")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "tickets" not in st.session_state:
    st.session_state.tickets = []

# Check if API key is stored safely in Streamlit Secrets (for online deployment)
secret_api_key = ""
try:
    if "GEMINI_API_KEY" in st.secrets:
        secret_api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

# Sidebar for Configuration, Multi-PDF Upload, Export & Ticket Logger
with st.sidebar:
    st.header("Configuration")
    if secret_api_key:
        api_key = secret_api_key
        st.success("✅ API Key configured securely")
    else:
        api_key = st.text_input("Enter Google Gemini API Key", type="password")

    st.divider()
    uploaded_files = st.file_uploader(
        "Upload IT Policy / Manual PDFs",
        type="pdf",
        accept_multiple_files=True,
    )

    st.divider()
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

    # Feature 2: Download Chat Transcript (.txt)
    if st.session_state.messages:
        transcript_lines = [
            f"IT Helpdesk Chat Transcript - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 50,
            "",
        ]
        for m in st.session_state.messages:
            role_label = "User" if m["role"] == "user" else "IT Bot"
            transcript_lines.append(f"{role_label}: {m['content']}\n")

        transcript_text = "\n".join(transcript_lines)
        st.download_button(
            label="📥 Download Chat Transcript (.txt)",
            data=transcript_text,
            file_name=f"it_helpdesk_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
        )

    # Feature 3: Quick IT Ticket Logger
    st.divider()
    st.subheader("🎫 Raise IT Ticket")
    with st.form("ticket_form", clear_on_submit=True):
        user_name = st.text_input("Your Name")
        issue_category = st.selectbox(
            "Category",
            ["Network / Wi-Fi / VPN", "Account / Password", "Software / Hardware", "Policy / Access", "Other"],
        )
        issue_desc = st.text_area("Issue Summary")
        submitted = st.form_submit_button("Submit Ticket")

        if submitted:
            if user_name.strip() and issue_desc.strip():
                ticket_id = f"TKT-{1001 + len(st.session_state.tickets)}"
                st.session_state.tickets.append(
                    {
                        "ticket_id": ticket_id,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "name": user_name.strip(),
                        "category": issue_category,
                        "issue": issue_desc.strip(),
                        "status": "Open",
                    }
                )
                st.success(f"Ticket {ticket_id} raised!")
            else:
                st.warning("Name and Issue Summary rendum fill pannunga.")

    if st.session_state.tickets:
        st.caption(f"Total Tickets Logged: {len(st.session_state.tickets)}")
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(
            csv_buffer,
            fieldnames=["ticket_id", "timestamp", "name", "category", "issue", "status"],
        )
        writer.writeheader()
        writer.writerows(st.session_state.tickets)

        st.download_button(
            label="📊 Download Tickets CSV",
            data=csv_buffer.getvalue(),
            file_name=f"it_tickets_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

# Feature 1: Extract text across multiple uploaded PDFs
combined_pdf_parts = []
if uploaded_files:
    for pdf_file in uploaded_files:
        try:
            reader = PdfReader(pdf_file)
            file_text = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    file_text.append(text)
            extracted = "\n".join(file_text).strip()
            if extracted:
                combined_pdf_parts.append(f"--- Document: {pdf_file.name} ---\n{extracted}")
                st.sidebar.success(f"{pdf_file.name} loaded ({len(reader.pages)} pages)")
            else:
                st.sidebar.warning(f"{pdf_file.name}-la text illa (scanned PDF-ah irukkalam).")
        except Exception as e:
            st.sidebar.error(f"Error reading {pdf_file.name}: {e}")

pdf_text = "\n\n".join(combined_pdf_parts)

# Display previous chat messages from history
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# User question input
user_query = st.chat_input("Type your IT issue here...")

if user_query:
    if not api_key:
        st.error("⚠️ Please enter your Google Gemini API Key in the sidebar first!")
    else:
        # Show user message immediately and save to history
        st.chat_message("user").write(user_query)
        st.session_state.messages.append({"role": "user", "content": user_query})

        try:
            client = genai.Client(api_key=api_key)
            safe_pdf_text = pdf_text[:30000] if pdf_text else "No PDF uploaded."

            # Include recent chat context for follow-up questions
            recent_history = "\n".join(
                [f"{m['role'].capitalize()}: {m['content']}" for m in st.session_state.messages[-6:]]
            )

            prompt = f"""
            You are a helpful IT Helpdesk Assistant.
            Answer the user's question accurately. If PDF context is provided, prioritize it.

            PDF Context:
            {safe_pdf_text}

            Recent Conversation:
            {recent_history}

            User Question: {user_query}
            """

            with st.spinner("IT Bot is thinking..."):
                available_models = [
                    m.name.replace("models/", "")
                    for m in client.models.list()
                    if "gemini" in m.name.lower()
                    and "flash" in m.name.lower()
                    and "image" not in m.name.lower()
                    and "tts" not in m.name.lower()
                ]

                models_to_try = ["gemini-3.8-flash"] + [m for m in available_models if m != "gemini-3.8-flash"]

                response = None
                errors = []
                for model_name in models_to_try[:5]:
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=prompt,
                        )
                        break
                    except Exception as model_err:
                        errors.append(f"**{model_name}**: {model_err}")
                        continue

                if response:
                    st.chat_message("assistant").write(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                else:
                    st.error("All tried models failed. Here are the exact errors:")
                    for err in errors:
                        st.write(err)

        except Exception as e:
            st.error(f"An error occurred: {e}")
