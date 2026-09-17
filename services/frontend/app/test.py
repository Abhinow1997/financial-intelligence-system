import streamlit as st
import pandas as pd
df = pd.DataFrame({
  'first column': [1, 2, 3, 4],
  'second column': [10, 20, 30, 40]
})

df

x = st.slider('x')  # 👈 this is a widget
st.write(x, 'squared is', x * x)

st.session_state['my_input'] = st.text_input("Enter some text") 
st.write("You entered: ", st.session_state['my_input'])