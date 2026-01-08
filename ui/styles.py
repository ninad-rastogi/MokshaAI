"""
UI styling and CSS for Moksha AI - Fixed sidebar with hover menu
"""

import streamlit as st


def inject_custom_css(theme: str = "dark"):
    """Inject custom CSS for fixed sidebar and hover menu"""

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
        menu_popup_bg = "#ffffff"
        menu_popup_border = "rgba(0, 0, 0, 0.15)"
        menu_shadow = "0 4px 12px rgba(0, 0, 0, 0.15)"

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
        menu_popup_bg = "#2a2a3e"
        menu_popup_border = "rgba(255, 255, 255, 0.2)"
        menu_shadow = "0 4px 12px rgba(0, 0, 0, 0.4)"

    st.markdown(
        f"""
        <style>
        /* Main container */
        .main {{
            padding-top: 2rem;
        }}
        
        /* FIXED SIDEBAR - NO RESIZE */
        [data-testid="stSidebar"] {{
            background: {sidebar_gradient};
            width: 300px !important;
            min-width: 300px !important;
            max-width: 300px !important;
        }}
        
        [data-testid="stSidebar"] > div:first-child {{
            background: {sidebar_gradient};
            width: 300px !important;
            overflow-y: auto !important;
            overflow-x: hidden !important;
            scroll-behavior: smooth;
        }}
        
        /* Hide resize handle */
        [data-testid="stSidebar"] [data-testid="stSidebarNav"]::before {{
            display: none !important;
        }}
        
        section[data-testid="stSidebar"] > div {{
            resize: none !important;
        }}
        
        /* Disable sidebar resizing completely */
        [data-testid="stSidebar"] .css-1544g2n {{
            pointer-events: none !important;
        }}
        
        /* Sidebar text colors */
        [data-testid="stSidebar"] .stMarkdown {{
            color: {sidebar_text};
        }}
        
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {{
            color: {sidebar_heading} !important;
        }}
        
        /* Sidebar dividers */
        [data-testid="stSidebar"] hr {{
            border-color: {sidebar_divider};
        }}
        
        /* Sidebar buttons - compact spacing */
        [data-testid="stSidebar"] button {{
            margin: 0.15rem 0;
            border-radius: 0.5rem;
            transition: all 0.3s ease;
        }}
        
        [data-testid="stSidebar"] button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
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
        .chat-item-container {{
            position: relative;
            margin-bottom: 0.5rem;
        }}
        
        .chat-button-wrapper {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.5rem;
        }}
        
        .chat-main-button {{
            flex: 1;
            text-align: left;
            padding: 0.5rem;
            background: {sidebar_button_bg};
            color: {sidebar_text};
            border: 1px solid {sidebar_button_border};
            border-radius: 0.5rem;
            cursor: pointer;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            transition: all 0.2s ease;
        }}
        
        .chat-main-button:hover {{
            background: {sidebar_button_hover_bg};
            transform: translateY(-2px);
        }}
        
        .chat-main-button.current-chat {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: 600;
        }}
        
        .three-dot-menu {{
            position: relative;
            display: inline-block;
        }}
        
        .three-dots {{
            font-size: 1.2rem;
            padding: 0.25rem 0.5rem;
            cursor: pointer;
            background: {sidebar_button_bg};
            border: 1px solid {sidebar_button_border};
            border-radius: 0.5rem;
            transition: all 0.2s ease;
        }}
        
        .three-dots:hover {{
            background: {sidebar_button_hover_bg};
        }}
        
        /* Hover menu - hidden by default */
        .hover-menu {{
            display: none;
            position: absolute;
            right: 0;
            top: 100%;
            margin-top: 0.25rem;
            background: {menu_popup_bg};
            border: 1px solid {menu_popup_border};
            border-radius: 0.5rem;
            box-shadow: {menu_shadow};
            z-index: 1000;
            min-width: 120px;
            padding: 0.25rem;
        }}
        
        /* Show menu on hover */
        .three-dot-menu:hover .hover-menu {{
            display: block;
        }}
        
        /* Keep menu visible when hovering over it */
        .hover-menu:hover {{
            display: block;
        }}
        
        .menu-action {{
            display: block;
            width: 100%;
            text-align: left;
            padding: 0.5rem 0.75rem;
            background: transparent;
            color: {sidebar_text};
            border: none;
            border-radius: 0.25rem;
            cursor: pointer;
            transition: all 0.2s ease;
            font-size: 0.9rem;
        }}
        
        .menu-action:hover {{
            background: {sidebar_button_hover_bg};
        }}
        
        .rename-action:hover {{
            background: rgba(0, 123, 255, 0.2) !important;
            border-color: rgba(0, 123, 255, 0.4);
        }}
        
        .delete-action:hover {{
            background: rgba(220, 53, 69, 0.2) !important;
            border-color: rgba(220, 53, 69, 0.4);
        }}
        
        /* Hide the actual Streamlit buttons used for functionality */
        [data-testid="stSidebar"] button[key*="sel_"],
        [data-testid="stSidebar"] button[key*="menu_"],
        [data-testid="stSidebar"] button[key*="ren_"],
        [data-testid="stSidebar"] button[key*="del_"] {{
            display: none !important;
        }}
        
        /* Show action buttons in rename/delete mode */
        [data-testid="stSidebar"] button[key*="save_"],
        [data-testid="stSidebar"] button[key*="cancel_"],
        [data-testid="stSidebar"] button[key*="yes_"],
        [data-testid="stSidebar"] button[key*="no_"] {{
            display: block !important;
        }}
        
        /* Save button styling */
        [data-testid="stSidebar"] button[key*="save_"] {{
            background: rgba(40, 167, 69, 0.2) !important;
            border-color: rgba(40, 167, 69, 0.4) !important;
        }}
        
        /* Expander styling in sidebar */
        [data-testid="stSidebar"] [data-testid="stExpander"] {{
            background: {sidebar_expander_bg};
            border: 1px solid {sidebar_button_border};
            border-radius: 0.5rem;
            margin: 0.5rem 0;
        }}
        
        [data-testid="stSidebar"] [data-testid="stExpander"]:hover {{
            background: {sidebar_button_hover_bg};
        }}
        
        /* Info and caption in sidebar */
        [data-testid="stSidebar"] .stAlert {{
            background: {sidebar_alert_bg};
            border: 1px solid {sidebar_alert_border};
            color: {sidebar_text};
        }}
        
        [data-testid="stSidebar"] .stCaption {{
            color: {sidebar_text};
            opacity: 0.6;
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
        
        /* Keep footer hidden */
        footer {{visibility: hidden;}}
        
        /* Better text input styling */
        .stTextInput input {{
            border-radius: 0.5rem;
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
            margin-bottom: 0.25rem;
        }}
        
        /* Warning styling */
        [data-testid="stSidebar"] .stAlert[data-baseweb="notification"] {{
            padding: 0.5rem;
            margin: 0.25rem 0;
        }}
        </style>
        
        <script>
        // Handle chat selection via custom HTML buttons
        document.addEventListener('click', function(e) {{
            if (e.target.classList.contains('chat-main-button')) {{
                const chatId = e.target.getAttribute('data-chat-id');
                // Trigger the hidden Streamlit button
                const streamlitBtn = document.querySelector(`button[key="sel_${{chatId}}"]`);
                if (streamlitBtn) streamlitBtn.click();
            }}
            
            if (e.target.classList.contains('menu-action')) {{
                const chatId = e.target.getAttribute('data-chat-id');
                const action = e.target.getAttribute('data-action');
                const streamlitBtn = document.querySelector(`button[key="${{action}}_${{chatId}}"]`);
                if (streamlitBtn) streamlitBtn.click();
            }}
        }});
        </script>
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
