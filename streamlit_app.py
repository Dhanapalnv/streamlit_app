import streamlit as st
from streamlit_option_menu import option_menu


menu_options = ["Channel_info", "View Table", "List of queries"]
with st.sidebar:
    selected = option_menu(None, menu_options, 
        icons=['info', 'question', "list-task"], 
        menu_icon="cast", default_index=0, orientation="vertical")
