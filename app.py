import streamlit as st
import requests
import json
import os

# 💡 API 정보
API_URL = 'https://ai.potens.ai/api/chat'
# API_KEY는 보안상의 이유로 직접 노출하지 않고 환경 변수 사용을 권장하지만, 테스트를 위해 유지합니다.
API_KEY = 'Bx5TQFcgJW76I3kmTnDfBrge4Mg117vv' 

# 📰 포텐스닷 API 호출 함수
def get_potens_response(keyword):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_KEY}'
    }
    
    # 📌 기능 수정: 키워드 관련 최신 기사 5개를 요약해 달라고 구체적으로 요청하는 프롬프트
    prompt_text = f"다음 키워드: '{keyword}'에 대한 최신 뉴스나 기사를 5개 찾아서, 각 기사를 간결하게 요약해주고 출처나 주요 내용을 표시해줘. 전체적으로 하나의 마크다운 문단으로 깔끔하게 작성해줘."
    data = {"prompt": prompt_text}
    
    try:
        response = requests.post(API_URL, headers=headers, data=json.dumps(data), timeout=60) # 타임아웃을 60초로 늘려 안정성 확보
        response.raise_for_status() 
        result = response.json()
        
        # 'content' 또는 'message' 필드를 확인하여 유효한 응답을 반환합니다.
        if 'content' in result and result['content']:
            return result['content']
        elif 'message' in result and result['message']:
            return result['message']
        else:
            return "[API_ERROR: Potens.ai API 응답에서 유효한 응답 필드를 찾을 수 없습니다.]"

    except requests.exceptions.HTTPError as e:
        return f"🚨 [HTTP ERROR {e.response.status_code}] API 호출 실패. 응답: {e.response.text}"
    except requests.exceptions.RequestException as e:
        return f"🚨 [NETWORK ERROR] API 호출 중 네트워크 문제가 발생했습니다: {e}"
    except Exception as e:
        return f"🚨 [PROCESSING ERROR] 예기치 않은 처리 문제가 발생했습니다: {e}"


# 🖼️ Streamlit 웹 인터페이스 구성 및 디자인 적용
st.set_page_config(page_title="AI 기반 뉴스 요약 엔진", layout="centered", initial_sidebar_state="collapsed")

# --- 커스텀 CSS (가독성 최우선 및 파란색 계열 유지) ---
st.markdown("""
    <style>
        /* 메인 색상 변수 설정 */
        :root {
            --primary-blue: #1E90FF; /* Dodgblue, 메인 파란색 */
            --light-blue: #E3F2FD; /* Light Blue 50, 배경 강조색 */
            --dark-blue: #1565C0; /* Blue 800, 진한 파란색 */
            --text-color: #333333; /* 📌 글씨색을 진한 회색으로 설정 */
        }
        
        /* 전체 배경색과 글씨색 설정 */
        .stApp {
            background-color: #FFFFFF; /* 흰색 배경 유지 */
            color: var(--text-color); /* 📌 기본 글씨색을 진하게 설정 */
        }
        
        /* 모든 텍스트의 기본 색상을 오버라이드 (가독성 확보) */
        body, p, div, span, h1, h2, h3, h4, .stText {
            color: var(--text-color) !important; 
        }

        /* 제목 스타일 */
        h1, h2, h3 {
            color: var(--dark-blue) !important;
        }

        /* 메인 헤더 스타일 */
        .header-title {
            text-align: center;
            color: var(--primary-blue);
            padding-top: 20px;
            font-size: 2.5em;
            font-weight: 700;
        }

        /* 설명 문구 스타일 */
        .header-subtitle {
            text-align: center;
            color: #616161; 
            margin-bottom: 40px;
            font-size: 1.1em;
        }

        /* 입력 필드 스타일 */
        .stTextInput > div > div > input {
            border: 2px solid var(--primary-blue);
            border-radius: 8px;
            padding: 10px 15px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            color: var(--text-color); /* 입력 텍스트 색상도 명확하게 */
        }
        
        /* 스피너 스타일 */
        .stSpinner > div > div {
            color: var(--primary-blue) !important;
        }

        /* 섹션 구분선 */
        hr {
            border-top: 3px solid var(--light-blue);
            margin: 30px 0;
        }
        
        /* 푸터 스타일 */
        .footer {
            position: fixed;
            left: 0;
            bottom: 0;
            width: 100%;
            background-color: var(--light-blue); 
            color: var(--dark-blue);
            text-align: center;
            padding: 10px;
            font-size: 0.85em;
            border-top: 1px solid var(--primary-blue);
            z-index: 100;
        }
    </style>
""", unsafe_allow_html=True)

# --- 헤더 및 검색창 섹션 ---
with st.container(border=False):
    st.markdown("<div class='header-title'>📰 AI 기반 뉴스 요약 엔진</div>", unsafe_allow_html=True)
    st.markdown("<div class='header-subtitle'>Potens.ai Chat API를 활용하여 입력 키워드에 대한 최신 기사 5개를 요약합니다.</div>", unsafe_allow_html=True)

    search_keyword = st.text_input(
        "키워드 입력", 
        key="keyword_input",
        placeholder="검색할 키워드를 입력하고 엔터를 누르세요 (예: 전력, AI 반도체)",
        label_visibility="collapsed"
    )

# --- 결과 섹션 ---
if search_keyword:
    st.markdown("---") 
    
    tab1, tab2 = st.tabs(["💡 뉴스 요약 결과", "🛠️ API 상세"])

    with tab1:
        with st.container(border=True): 
            st.markdown(f"### **'{search_keyword}'** 키워드 최신 뉴스 분석 결과")
            
            # 스피너에 요약 기능임을 명확히 표시
            with st.spinner('⏳ Potens.ai API가 최신 뉴스 5개를 요약하고 있습니다... (최대 60초 소요)'):
                response_text = get_potens_response(search_keyword)
            
            # API 오류 메시지 필터링 및 처리
            if response_text.startswith("[API_ERROR:") or response_text.startswith("🚨"):
                st.error("⚠️ 죄송합니다. API 호출 또는 응답 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")
            else:
                st.markdown(response_text)
                st.info(f"✨ '{search_keyword}'에 대한 뉴스 요약 5건이 완료되었습니다.")

    with tab2:
        st.subheader("개발자/디버깅 정보")
        st.code(f"API URL: {API_URL}")
        st.code(f"요청 키워드: {search_keyword}")
        
        if response_text.startswith("[API_ERROR:") or response_text.startswith("🚨"):
             st.error(f"상세 오류 메시지: {response_text}")
        else:
             st.success("API 호출이 성공적으로 처리되었으며, 요약된 응답이 수신되었습니다.")
             st.markdown("---")
             st.caption("AI에게 전달된 프롬프트:")
             st.code(f"다음 키워드: '{search_keyword}'에 대한 최신 뉴스나 기사를 5개 찾아서, 각 기사를 간결하게 요약해주고 출처나 주요 내용을 표시해줘. 전체적으로 하나의 마크다운 문단으로 깔끔하게 작성해줘.")
        
# --- 푸터 섹션 ---
st.markdown("""
    <div class="footer">AI 기반 정보 검색기 | Powered by Potens.ai</div>
""", unsafe_allow_html=True)