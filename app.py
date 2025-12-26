import streamlit as st
import pandas as pd
from supabase import create_client
import requests

st.set_page_config(page_title="생산관리 AI 챗봇", layout="wide")

# --- [수정됨] 키를 코드에 직접 적지 않고, 서버 설정(Secrets)에서 가져옵니다 ---
try:
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
    POTENS_API_KEY = st.secrets["potens"]["api_key"]
except Exception as e:
    st.error("🚨 서버에 비밀 키(Secrets)가 설정되지 않았습니다.")
    st.stop()

# DB 연결
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"DB 연결 실패: {e}")
    st.stop()

# --- 이하 로직은 동일합니다 ---
def fetch_production_data():
    try:
        response = supabase.table("production_plans")\
            .select("*")\
            .order("plan_date", desc=False)\
            .limit(2000)\
            .execute()
        if response.data:
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

def ask_ai(query, df):
    url = "https://ai.potens.ai/api/chat"
    headers = {
        "Content-Type": "application/json", 
        "Authorization": f"Bearer {POTENS_API_KEY}"
    }
    
    if not df.empty:
        summary = df.groupby(['plan_date', 'line', 'category'])['quantity'].sum().reset_index()
        data_context = summary.to_string(index=False)
    else:
        data_context = "데이터가 없습니다."

    system_prompt = f"""
    당신은 공장 생산 계획을 관리하는 '수석 스케줄러 AI'입니다.
    아래 [데이터베이스 요약]을 바탕으로 질문에 답변하세요.
    
    [데이터베이스 요약]
    {data_context}

    [답변 규칙]
    1. 데이터에 근거해서 답변하세요.
    2. 구체적인 날짜, 라인, 수량을 언급하세요.
    """

    payload = {"prompt": f"{system_prompt}\n\n[사용자 질문]: {query}"}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        if response.status_code == 200:
            return response.json().get('message', '오류')
        return f"연결 실패: {response.text}"
    except Exception as e:
        return f"통신 오류: {str(e)}"

# 화면 UI
st.title("🏭 생산계획 AI 관제 센터 (Web Ver)")

col1, col2 = st.columns([1.5, 1])
df_data = fetch_production_data()

with col1:
    st.subheader("💬 AI 스케줄러")
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "안녕하세요! 무엇을 도와드릴까요?"}]

    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input("질문을 입력하세요"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)
        with st.chat_message("assistant"):
            with st.spinner("분석 중..."):
                if df_data.empty:
                    st.write("데이터가 없습니다.")
                else:
                    ans = ask_ai(prompt, df_data)
                    st.write(ans)
                    st.session_state.messages.append({"role": "assistant", "content": ans})

with col2:
    st.subheader("📊 데이터 조회")
    if not df_data.empty:
        st.dataframe(df_data[['plan_date', 'line', 'category', 'product_name', 'quantity']])
