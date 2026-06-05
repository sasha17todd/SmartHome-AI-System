import streamlit as st
from openai import AzureOpenAI
import json
import re
import asyncio
# Official Azure IoT Hub Device SDK components
from azure.iot.device.aio import IoTHubDeviceClient
from azure.iot.device import Message

# ==========================================
# 1. ENTERPRISE CLOUD CONFIGURATION
# ==========================================
AI_ENDPOINT = st.secrets["AI_ENDPOINT"]
AI_KEY = st.secrets["AI_KEY"]
DEPLOYMENT_NAME = "gpt-4o-mini"

# Secure primary connection string for your pre-configured Azure IoT Hub resource
IOT_CONNECTION_STRING = st.secrets["IOT_CONNECTION_STRING"]

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

# Asynchronous worker function to stream live telemetry into your Azure IoT Hub
async def send_azure_iot_telemetry(temperature, ac_status, light_hex):
    try:
        # Initialize the secure MQTT client wrapper using the cloud secrets token
        device_client = IoTHubDeviceClient.create_from_connection_string(IOT_CONNECTION_STRING)
        await device_client.connect()
        
        # Package raw localized state variables into a structured IoT payload
        telemetry_payload = {
            "temperature": temperature,
            "ac_status": ac_status,
            "current_light_hex": light_hex
        }
        
        # Serialize dictionary to an unformatted JSON string wrapper
        msg = Message(json.dumps(telemetry_payload))
        msg.content_encoding = "utf-8"
        msg.content_type = "application/json"
        
        # Dispatch live payload stream directly to the infrastructure
        await device_client.send_message(msg)
        await device_client.shutdown()
        return True
    except Exception:
        return False

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

# Calculate optimal contrast typography tone depending on background brightness values
def get_contrast_color(hex_str):
    hex_str = hex_str.lstrip('#')
    r, g, b = tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#111111" if luminance > 0.5 else "#FFFFFF"

chosen_text = get_contrast_color(chosen_bg)

# Explicit layout declarations for the left-side panel theme settings
SIDEBAR_BG = "#121316"
SIDEBAR_TEXT = "#FFFFFF"
SIDEBAR_WIDGET_BG = "#1A1C23"
SIDEBAR_BORDER = "#2D313E"

# ADVANCED GLOBAL CUSTOM CSS INJECTION LOOP
st.markdown(
    f"""
    <style>
    /* 1. RIGHT PANEL AREA (MAIN APPLICATION INTERFACE) styling */
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
    
    /* User Input Text Box Override - Enforces clean solid white background with crisp dark values */
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
    
    /* Command Button Layout Styling - Nullifies native Streamlit runtime dark theme font inversion */
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
    .stButton > button p, .stButton > button div, .stButton > button span {{
        color: #111111 !important;
        -webkit-text-fill-color: #111111 !important;
    }}
    
    /* Hover Interaction Fix - Controls safe transformation transitions into subtle soft gray steps */
    .stButton > button:hover {{
        background-color: #E6E6E6 !important;
        border: 2px solid #111111 !important;
    }}
    .stButton > button:hover p, .stButton > button:hover div, .stButton > button:hover span {{
        color: #111111 !important;
        -webkit-text-fill-color: #111111 !important;
    }}
    
    /* 2. LEFT PANEL AREA (SIDEBAR CONTROL SIMULATOR) locked layout styling */
    section[data-testid="stSidebar"] {{
        background-color: {SIDEBAR_BG} !important;
        border-right: 1px solid {SIDEBAR_BORDER} !important;
    }}
    section[data-testid="stSidebar"] * {{
        color: {SIDEBAR_TEXT} !important;
    }}
    section[data-testid="stSidebar"] div[data-baseweb="select"] {{
        background-color: {SIDEBAR_WIDGET_BG} !important;
        border: 1px solid {SIDEBAR_BORDER} !important;
        border-radius: 8px !important;
    }}
    section[data-testid="stSidebar"] div[data-baseweb="select"] * {{
        color: {SIDEBAR_TEXT} !important;
    }}
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
st.write("Interact with your home using natural language powered by Azure AI Foundry and Azure IoT Hub.")

user_command = st.text_input("Enter your command for the house:", placeholder="e.g., Turn off the lights and set temperature to 21 degrees")

if st.button("Send Command"):
    if user_command:
        # PIPELINE 1: Stream real-time edge metric values to your live Azure IoT Hub infrastructure
        with st.spinner("📡 Transmitting real-time telemetry to Azure IoT Hub..."):
            iot_success = asyncio.run(send_azure_iot_telemetry(current_temp, ac_status, st.session_state.current_light_hex))
            if iot_success:
                st.sidebar.success("⚡ IoT Hub: Connected & Sent!")
            else:
                st.sidebar.error("❌ IoT Hub: Telemetry Failed")

        # PIPELINE 2: Request structured behavioral directives from Azure OpenAI endpoint
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
            
            # Sanitization loop: Sanitizes loose or trailing markdown container parameters from raw stream
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