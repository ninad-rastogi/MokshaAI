"""
UI styling and CSS for Moksha AI
"""

import streamlit as st


def inject_custom_css():
    """Inject custom CSS for better UI"""

    st.markdown(
        """
        <style>
        /* Main container */
        .main {
            padding-top: 2rem;
        }
        
        /* Sidebar styling */
        [data-testid="stSidebar"] {
            background-color: var(--background-color);
        }
        
        /* Better button alignment in sidebar */
        [data-testid="stSidebar"] button {
            margin: 0.25rem 0;
        }
        
        /* Chat item container */
        [data-testid="stSidebar"] .stButton {
            margin-bottom: 0.25rem;
        }
        
        /* Align action buttons horizontally */
        [data-testid="stSidebar"] [data-testid="column"] {
            display: flex;
            align-items: center;
            gap: 0.25rem;
        }
        
        /* Make small buttons consistent */
        [data-testid="stSidebar"] button[kind="secondary"] {
            padding: 0.25rem 0.5rem;
            min-height: 2rem;
        }
        
        /* Chat history items */
        .chat-history-item {
            margin-bottom: 0.5rem;
            padding: 0.5rem;
            border-radius: 0.5rem;
            transition: background-color 0.2s;
        }
        
        .chat-history-item:hover {
            background-color: rgba(128, 128, 128, 0.1);
        }
        
        /* New chat button */
        .new-chat-btn {
            width: 100%;
            padding: 0.75rem;
            margin-bottom: 1rem;
            background-color: var(--primary-color);
            color: white;
            border: none;
            border-radius: 0.5rem;
            cursor: pointer;
            font-weight: 500;
            transition: opacity 0.2s;
        }
        
        .new-chat-btn:hover {
            opacity: 0.8;
        }
        
        /* Thinking animation */
        .thinking-dots span {
            display: inline-block;
            font-size: 20px;
            animation: bounce 1.4s infinite;
        }
        
        .thinking-dots span:nth-child(2) {
            animation-delay: 0.2s;
        }
        
        .thinking-dots span:nth-child(3) {
            animation-delay: 0.4s;
        }
        
        @keyframes bounce {
            0%, 80%, 100% { transform: scale(0); opacity: 0; }
            40% { transform: scale(1); opacity: 1; }
        }
        
        /* Source citation styling */
        .source-box {
            background-color: rgba(128, 128, 128, 0.1);
            border-left: 3px solid var(--primary-color);
            padding: 0.75rem;
            margin-top: 1rem;
            border-radius: 0.25rem;
        }
        
        .source-title {
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: var(--primary-color);
        }
        
        /* Chat message improvements */
        .chat-message {
            animation: fadeIn 0.3s ease-in;
        }
        
        @keyframes fadeIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        /* Scripture badge */
        .scripture-badge {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            background-color: rgba(255, 165, 0, 0.2);
            border-radius: 0.25rem;
            font-size: 0.875rem;
            font-weight: 500;
            margin-right: 0.5rem;
        }
        
        /* Page number badge */
        .page-badge {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            background-color: rgba(0, 123, 255, 0.2);
            border-radius: 0.25rem;
            font-size: 0.875rem;
            margin-right: 0.5rem;
        }
        
        /* Better spacing for expanders */
        [data-testid="stExpander"] {
            margin: 0.5rem 0;
        }
        
        /* Smooth transitions */
        button, .stButton button {
            transition: all 0.2s ease;
        }
        
        /* Hide streamlit branding in small screens */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* Better text input styling */
        .stTextInput input {
            border-radius: 0.5rem;
        }
        
        /* Chat input styling */
        [data-testid="stChatInput"] {
            border-radius: 1rem;
        }
        
        /* Scrollbar styling */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: transparent;
        }
        
        ::-webkit-scrollbar-thumb {
            background: rgba(128, 128, 128, 0.3);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(128, 128, 128, 0.5);
        }
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
