import streamlit as st
from openai import AzureOpenAI
import json
import re

# ==========================================
# 1. AZURE AI FOUNDRY CONFIGURATION
# ==========================================
AI_ENDPOINT = st.secrets["AI_ENDPOINT"]
AI_KEY = st.secrets["AI_KEY"]
DEPLOYMENT_NAME = "gpt-4o-mini"

# Initialize Azure OpenAI Client
client = AzureOpenAI(
    azure_endpoint=AI_ENDPOINT,
    api_key=AI_KEY,
    api_version="2024-02-15-preview"
)

SYSTEM_PROMPT = """
You are the ultimate intelligent brain of a Smart Home Automation system.
Analyze the current room conditions and the user's request, then control BOTH the climate and the smart lighting ambiance.

You must respond EXCLUSIVELY in a valid JSON format containing exactly four fields. Do not include markdown code blocks (like ```json) in your response.
1. "response": A friendly text response for the user in English.
2. "climate_action": Options: "SET_TEMPERATURE", "TURN_OFF_AC", "NOTHING".
3. "target_temp": A float number for the new temperature. (If no climate change, keep it equal to current room temp).
4. "light_hex": A string representing a valid 6-character Hexadecimal color code (e.g., "#FFFFFF", "#FF9900") that perfectly matches the user's requested mood or command.
   - FIX: If they ask to "turn on the lights", "light up", or want normal/bright white lighting, generate a clean white hex code ("#FFFFFF").
   - If they ask for "golden hour", generate a warm amber/sunset hex code.
   - If they want to sleep or turn off, generate a very dark or black code ("#0A0A0A").
   - If they ask for a specific mood (party, neon, ocean, forest, beach), translate that mood into a beautiful background Hex color.
   - If they don't mention lighting or ambiance, maintain the current hex color provided in the context.
"""

# ==========================================
# 2. STATE INITIALIZATION & DESIGN CALCULATIONS
# ==========================================
if "current_temp_val" not in st.session_state:
    st.session_state.current_temp_val = 22.0
if "ac_status_val" not in st.session_state:
    st.session_state.ac_status_val = "OFF"
if "current_light_hex" not in st.session_state:
    st.session_state.current_light_hex = "#ffffff"

chosen_bg = st.session_state.current_light_hex

# Dynamically calculate main UI contrast text color based on AI generated background brightness
def get_contrast_color(hex_str):
    hex_str = hex_str.lstrip('#')
    r, g, b = tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#111111" if luminance > 0.5 else "#FFFFFF"

chosen_text = get_contrast_color(chosen_bg)

# Define a static dark theme layout for the left-side panel (Sidebar)
SIDEBAR_BG = "#121316"
SIDEBAR_TEXT = "#FFFFFF"
SIDEBAR_WIDGET_BG = "#1A1C23"
SIDEBAR_BORDER = "#2D313E"

# ADVANCED CUSTOM CSS INJECTION
st.markdown(
    f"""
    <style>
    /* 1. RIGHT PANEL AREA (MAIN APPLICATION INTERFACE) */
    .stApp {{
        background-color: {chosen_bg} !important;
        color: {chosen_text} !important;
        transition: background-color 0.8s ease;
    }}
    header[data-testid="stHeader"] {{
        background-color: transparent !important;
    }}
    .stApp h1, .stApp p, .stApp span, .stApp label {{
        color: {chosen_text} !important;
    }}
    
    /* User Input Text Box Override - Forced Clean White Background with Intense Dark Text */
    div[data-testid="stTextInput"] div[data-baseweb="input"],
    div[data-testid="stTextInput"] div[data-baseweb="input"] > div {{
        background-color: #FFFFFF !important;
        border: 2px solid #111111 !important;
        border-radius: 8px !important;
    }}
    div[data-testid="stTextInput"] input {{
        color: #111111 !important;
        background-color: #FFFFFF !important;
        -webkit-text-fill-color: #111111 !important;
    }}
    div[data-testid="stTextInput"] input::placeholder {{
        color: #666666 !important;
    }}
    
    /* Command Button Layout Styling - Locks Text to Dark Regardless of Underlying Page Theme */
    .stButton > button {{
        background-color: #FFFFFF !important;
        color: #111111 !important;
        border: 2px solid #111111 !important;
        font-weight: bold !important;
        border-radius: 8px !important;
        padding: 10px !important;
        width: 100% !important;
        transition: background-color 0.2s ease;
    }}
    
    /* Forces internal component typography elements to stay dark */
    .stButton > button p, .stButton > button div, .stButton > button span {{
        color: #111111 !important;
        -webkit-text-fill-color: #111111 !important;
    }}
    
    /* Hover Interaction Fix - Switches to Soft Light Gray instead of solid dark background masks */
    .stButton > button:hover {{
        background-color: #E6E6E6 !important;
        border: 2px solid #111111 !important;
    }}
    .stButton > button:hover p, .stButton > button:hover div, .stButton > button:hover span {{
        color: #111111 !important;
        -webkit-text-fill-color: #111111 !important;
    }}
    
    /* 2. LEFT PANEL AREA (SIDEBAR CONTROL SIMULATOR - LOCKED DARK DESIGN) */
    section[data-testid="stSidebar"] {{
        background-color: {SIDEBAR_BG} !important;
        border-right: 1px solid {SIDEBAR_BORDER} !important;
    }}
    section[data-testid="stSidebar"] * {{
        color: {SIDEBAR_TEXT} !important;
    }}
    
    /* AC Selection Box in Sidebar */
    section[data-testid="stSidebar"] div[data-baseweb="select"] {{
        background-color: {SIDEBAR_WIDGET_BG} !important;
        border: 1px solid {SIDEBAR_BORDER} !important;
        border-radius: 8px !important;
    }}
    section[data-testid="stSidebar"] div[data-baseweb="select"] * {{
        color: {SIDEBAR_TEXT} !important;
    }}
    
    /* Open Listbox Dropdown Menus Inside the Sidebar Context */
    div[role="listbox"] {{
        background-color: {SIDEBAR_WIDGET_BG} !important;
        border: 1px solid {SIDEBAR_BORDER} !important;
    }}
    div[role="listbox"] ul li {{
        color: {SIDEBAR_TEXT} !important;
        background-color: {SIDEBAR_WIDGET_BG} !important;
    }}
    div[role="listbox"] ul li:hover {{
        background-color: {SIDEBAR_BORDER} !important;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# ==========================================
# 3. SIDEBAR SIMULATOR CONTROL
# ==========================================
st.sidebar.header("📊 Live Sensor Telemetry")
current_temp = st.sidebar.slider("Simulated Room Temperature (°C)", 15.0, 35.0, value=st.session_state.current_temp_val)
ac_status = st.sidebar.selectbox("Current AC Status", ["OFF", "ON"], index=0 if st.session_state.ac_status_val == "OFF" else 1)

st.sidebar.markdown(f"🎨 **Ambiance Hex:** `{st.session_state.current_light_hex}`")

st.session_state.current_temp_val = current_temp
st.session_state.ac_status_val = ac_status

# ==========================================
# 4. MAIN USER INTERACTION
# ==========================================
st.title("🏠 Smart Home AI Automation")
st.write("Interact with your home using natural language powered by Azure AI Foundry.")

user_command = st.text_input("Enter your command for the house:", placeholder="e.g., Turn off the lights and set temperature to 21 degrees")

if st.button("Send Command"):
    if user_command:
        st.write("🔄 *Azure AI Agent is updating home ambient parameters...*")
        
        house_context = f"Current Temp: {current_temp}°C, AC Status: {ac_status}, Current Light Hex: {st.session_state.current_light_hex}. User request: {user_command}"
        
        try:
            response = client.chat.completions.create(
                model=DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": house_context}
                ],
                temperature=0.1
            )
            
            raw_content = response.choices[0].message.content.strip()
            
            # SANITIZATION FILTER: Strips out unintended markdown formatting wrappers
            if raw_content.startswith("```"):
                raw_content = re.sub(r"^```[a-zA-Z]*\n", "", raw_content)
                raw_content = re.sub(r"\n```$", "", raw_content)
            
            result_json = json.loads(raw_content.strip())
            st.success(f"🤖 **AI Agent Response:** {result_json['response']}")
            
            climate_action = result_json["climate_action"]
            ai_target_temp = float(result_json["target_temp"])
            ai_light_hex = result_json["light_hex"]
            
            if climate_action == "SET_TEMPERATURE":
                st.session_state.current_temp_val = ai_target_temp
                st.session_state.ac_status_val = "ON"
            elif climate_action == "TURN_OFF_AC":
                st.session_state.ac_status_val = "OFF"
                
            st.session_state.current_light_hex = ai_light_hex
            st.rerun()
                
        except Exception as e:
            st.error(f"Error parsing agent decision: {e}")