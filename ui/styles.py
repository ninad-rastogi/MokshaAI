"""
UI styling and CSS for Moksha AI - Theme-aware design with hover menu
"""

import streamlit as st


def inject_custom_css(theme: str = "dark"):
    """Inject custom CSS for beautiful UI with theme support and hover menu"""

    # Theme-specific colors
    if theme == "light":
        sidebar_gradient = "linear-gradient(180deg, #f0f2f6 0%, #e8eaf0 100%)"
        sidebar_text = "#1f1f1f"
        sidebar_heading = "#1f1f1f"
        sidebar_divider = "rgba(0, 0, 0, 0.1)"
        sidebar_button_bg = "rgba(0, 0, 0, 0.05)"
        sidebar_button_border = "rgba(0, 0, 0, 0.1)"
        sidebar_button_hover_bg = "rgba(0, 0, 0, 0.1)"
        sidebar_expander_bg = "rgba(0, 0, 0, 0.03)"
        sidebar_alert_bg = "rgba(102, 126, 234, 0.1)"
        sidebar_alert_border = "rgba(102, 126, 234, 0.3)"

    else:
        sidebar_gradient = "linear-gradient(180deg, #1a1a2e 0%, #16213e 100%)"
        sidebar_text = "#e0e0e0"
        sidebar_heading = "#f0f0f0"
        sidebar_divider = "rgba(255, 255, 255, 0.1)"
        sidebar_button_bg = "rgba(255, 255, 255, 0.05)"
        sidebar_button_border = "rgba(255, 255, 255, 0.1)"
        sidebar_button_hover_bg = "rgba(255, 255, 255, 0.1)"
        sidebar_expander_bg = "rgba(255, 255, 255, 0.03)"
        sidebar_alert_bg = "rgba(102, 126, 234, 0.1)"
        sidebar_alert_border = "rgba(102, 126, 234, 0.3)"

    st.markdown(
        f"""
        <style>
        /* Main container */
        .main {{
            padding-top: 2rem;
        }}
        
        /* Sidebar - FIXED WIDTH (not resizable) */
        [data-testid="stSidebar"] {{
            background: {sidebar_gradient};
            width: 300px !important;
            min-width: 300px !important;
            max-width: 300px !important;
        }}
        
        [data-testid="stSidebar"] > div:first-child {{
            background: {sidebar_gradient};
            overflow-y: auto !important;
            overflow-x: hidden !important;
            width: 300px !important;
            min-width: 300px !important;
            max-width: 300px !important;
            scroll-behavior: smooth;
        }}
        
        /* Sidebar text colors and sizing */
        [data-testid="stSidebar"] .stMarkdown {{
            color: {sidebar_text};
            font-size: 0.875rem;
        }}
        
        [data-testid="stSidebar"] h1 {{
            color: {sidebar_heading} !important;
            font-size: 1.25rem !important;
            margin-bottom: 0.25rem !important;
        }}
        
        [data-testid="stSidebar"] h2 {{
            color: {sidebar_heading} !important;
            font-size: 1.1rem !important;
            margin-bottom: 0.25rem !important;
        }}
        
        [data-testid="stSidebar"] h3 {{
            color: {sidebar_heading} !important;
            font-size: 0.95rem !important;
            margin-bottom: 0.25rem !important;
        }}
        
        /* Sidebar dividers */
        [data-testid="stSidebar"] hr {{
            border-color: {sidebar_divider};
            margin: 0.5rem 0 !important;
        }}
        
        /* Sidebar buttons - compact spacing */
        [data-testid="stSidebar"] button {{
            margin: 0.1rem 0 !important;
            padding: 0.5rem 0.75rem !important;
            font-size: 0.875rem !important;
            border-radius: 0.5rem;
            transition: all 0.3s ease;
            min-height: 2rem !important;
        }}
        
        [data-testid="stSidebar"] button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }}
        
        /* Chat button text truncation with ellipsis */
        [data-testid="stSidebar"] button[kind="secondary"] p,
        [data-testid="stSidebar"] button[kind="primary"] p {{
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 100%;
            display: block;
            font-size: 0.875rem !important;
        }}
        
        /* Primary button in sidebar */
        [data-testid="stSidebar"] button[kind="primary"] {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: 600;
        }}
        
        [data-testid="stSidebar"] button[kind="primary"]:hover {{
            background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
        }}
        
        /* Secondary buttons in sidebar */
        [data-testid="stSidebar"] button[kind="secondary"] {{
            background: {sidebar_button_bg};
            color: {sidebar_text};
            border: 1px solid {sidebar_button_border};
        }}
        
        [data-testid="stSidebar"] button[kind="secondary"]:hover {{
            background: {sidebar_button_hover_bg};
            border-color: {sidebar_button_border};
        }}
        
        /* HOVER-BASED 3-DOT MENU */
        /* Chat row container */
        [data-testid="stSidebar"] [data-testid="column"]:has(button[key*="select_"]) {{
            position: relative;
        }}
        
        /* 3-dot button styling */
        [data-testid="stSidebar"] button[key*="ren_"],
        [data-testid="stSidebar"] button[key*="del_"] {{
            padding: 0.25rem 0.5rem;
            min-height: 2rem;
            font-size: 0.875rem;
            opacity: 0;
            transition: opacity 0.2s ease;
        }}
        
        /* Show action buttons on hover of the row */
        [data-testid="stSidebar"] [data-testid="column"]:hover button[key*="ren_"],
        [data-testid="stSidebar"] [data-testid="column"]:hover button[key*="del_"] {{
            opacity: 1;
        }}
        
        /* Keep buttons visible when interacting with them */
        [data-testid="stSidebar"] button[key*="ren_"]:hover,
        [data-testid="stSidebar"] button[key*="del_"]:hover {{
            opacity: 1 !important;
        }}
        
        /* Make delete button red on hover */
        [data-testid="stSidebar"] button[key*="del_"]:hover {{
            background: rgba(220, 53, 69, 0.2) !important;
            border-color: rgba(220, 53, 69, 0.4) !important;
        }}
        
        /* Make rename button blue on hover */
        [data-testid="stSidebar"] button[key*="ren_"]:hover {{
            background: rgba(0, 123, 255, 0.2) !important;
            border-color: rgba(0, 123, 255, 0.4) !important;
        }}
        
        /* Compact action buttons layout */
        [data-testid="stSidebar"] [data-testid="column"]:has(button[key*="ren_"]) {{
            padding: 0 !important;
            gap: 0.1rem !important;
        }}
        
        /* Expander styling in sidebar */
        [data-testid="stSidebar"] [data-testid="stExpander"] {{
            background: {sidebar_expander_bg};
            border: 1px solid {sidebar_button_border};
            border-radius: 0.5rem;
            margin: 0.35rem 0 !important;
        }}
        
        [data-testid="stSidebar"] [data-testid="stExpander"]:hover {{
            background: {sidebar_button_hover_bg};
            border-color: {sidebar_button_border};
        }}
        
        /* Chat item styling - remove extra spacing */
        .stButton button {{
            text-align: left;
        }}
        
        /* Info and caption in sidebar */
        [data-testid="stSidebar"] .stAlert {{
            background: {sidebar_alert_bg};
            border: 1px solid {sidebar_alert_border};
            color: {sidebar_text};
            font-size: 0.8rem !important;
            padding: 0.5rem !important;
            margin: 0.25rem 0 !important;
        }}
        
        [data-testid="stSidebar"] .stCaption {{
            color: {sidebar_text};
            opacity: 0.6;
            font-size: 0.75rem !important;
        }}
        
        /* Thinking animation */
        .thinking-dots span {{
            display: inline-block;
            font-size: 20px;
            animation: bounce 1.4s infinite;
        }}
        
        .thinking-dots span:nth-child(2) {{
            animation-delay: 0.2s;
        }}
        
        .thinking-dots span:nth-child(3) {{
            animation-delay: 0.4s;
        }}
        
        @keyframes bounce {{
            0%, 80%, 100% {{ transform: scale(0); opacity: 0; }}
            40% {{ transform: scale(1); opacity: 1; }}
        }}
        
        /* Source citation styling */
        .source-box {{
            background-color: rgba(128, 128, 128, 0.1);
            border-left: 3px solid var(--primary-color);
            padding: 0.75rem;
            margin-top: 1rem;
            border-radius: 0.25rem;
        }}
        
        .source-title {{
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: var(--primary-color);
        }}
        
        /* Chat message improvements */
        .chat-message {{
            animation: fadeIn 0.3s ease-in;
        }}
        
        @keyframes fadeIn {{
            from {{
                opacity: 0;
                transform: translateY(10px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
        
        /* Scripture badge */
        .scripture-badge {{
            display: inline-block;
            padding: 0.25rem 0.5rem;
            background-color: rgba(255, 165, 0, 0.2);
            border-radius: 0.25rem;
            font-size: 0.75rem;
            font-weight: 500;
            margin-right: 0.5rem;
        }}
        
        /* Page number badge */
        .page-badge {{
            display: inline-block;
            padding: 0.25rem 0.5rem;
            background-color: rgba(0, 123, 255, 0.2);
            border-radius: 0.25rem;
            font-size: 0.75rem;
            margin-right: 0.5rem;
        }}
        
        /* Better spacing for expanders */
        [data-testid="stExpander"] {{
            margin: 0.35rem 0 !important;
        }}
        
        /* Smooth transitions */
        button, .stButton button {{
            transition: all 0.2s ease;
        }}
        
        /* Keep footer hidden but show main menu (settings) */
        footer {{visibility: hidden;}}
        
        /* Better text input styling */
        .stTextInput input {{
            border-radius: 0.5rem;
            font-size: 0.875rem;
        }}
        
        /* Chat input styling */
        [data-testid="stChatInput"] {{
            border-radius: 1rem;
        }}
        
        /* Scrollbar styling */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        
        ::-webkit-scrollbar-track {{
            background: transparent;
        }}
        
        ::-webkit-scrollbar-thumb {{
            background: rgba(128, 128, 128, 0.3);
            border-radius: 4px;
        }}
        
        ::-webkit-scrollbar-thumb:hover {{
            background: rgba(128, 128, 128, 0.5);
        }}
        
        /* Sidebar scrollbar */
        [data-testid="stSidebar"] ::-webkit-scrollbar-thumb {{
            background: {sidebar_button_border};
        }}
        
        [data-testid="stSidebar"] ::-webkit-scrollbar-thumb:hover {{
            background: {sidebar_button_hover_bg};
        }}
        
        /* Compact container spacing */
        [data-testid="stSidebar"] .element-container {{
            margin-bottom: 0.15rem !important;
        }}
        
        /* Warning styling */
        [data-testid="stSidebar"] .stAlert[data-baseweb="notification"] {{
            padding: 0.5rem;
            margin: 0.15rem 0;
        }}
        
        /* Prevent layout shift during hover */
        [data-testid="stSidebar"] [data-testid="column"] {{
            min-height: 2.5rem;
            overflow: hidden !important;
        }}
        
        /* Close button (X) - ensure full visibility and prevent overflow */
        [data-testid="stSidebar"] button[key*="close_"] {{
            padding: 0.25rem 0.35rem !important;
            min-width: 2rem !important;
            width: 2rem !important;
            height: 2.5rem !important;
            flex-shrink: 0 !important;
            font-size: 0.875rem !important;
            opacity: 1 !important;
        }}
        </style>
    """,
        unsafe_allow_html=True,
    )


def get_theme_colors(theme: str) -> dict:
    """Get color scheme based on theme"""

    if theme == "light":
        return {
            "bot_bg": "#b2f7ef",
            "bot_font": "#4d0810",
            "user_bg": "#7bdff2",
            "user_font": "#4d0810",
        }

    else:
        return {
            "bot_bg": "#124336",
            "bot_font": "#E6F9E6",
            "user_bg": "#13233A",
            "user_font": "#E6F7FF",
        }
