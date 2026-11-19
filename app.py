import streamlit as st
from google import genai
from pypdf import PdfReader

st.set_page_config(page_title="IT Helpdesk Bot", page_icon="🤖", layout="centered")

st.title("🤖 IT Helpdesk Bot")
st.write("Ask your IT questions or upload your company IT manual PDF for instant help!")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Check if API key is stored safely in Streamlit Secrets (for online deployment)
secret_api_key = ""
try:
    if "GEMINI_API_KEY" in st.secrets:
        secret_api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

# Sidebar for Configuration & PDF Upload
with st.sidebar:
    st.header("Configuration")
    if secret_api_key:
        api_key = secret_api_key
        st.success("✅ API Key configured securely")
    else:
        api_key = st.text_input("Enter Google Gemini API Key", type="password")
    
    st.divider()
    uploaded_file = st.file_uploader("Upload IT Policy / Manual (PDF)", type="pdf")
    
    st.divider()
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

# Extract text from PDF if uploaded
pdf_text = ""
if uploaded_file is not None:
    try:
        reader = PdfReader(uploaded_file)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pdf_text += text + "\n"
        if pdf_text.strip():
            st.sidebar.success(f"PDF loaded! ({len(reader.pages)} pages)")
        else:
            st.sidebar.warning("PDF-la text illa (idhu scanned image PDF-ah irukkalam).")
    except Exception as e:
        st.sidebar.error(f"Error reading PDF: {e}")

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