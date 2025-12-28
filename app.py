# app.py
import streamlit as st
import pandas as pd
from supabase import create_client
import requests

st.set_page_config(page_title="생산관리 AI 챗봇", layout="wide")

try:
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
    POTENS_API_KEY = "Bx5TQFcgJW76I3kmTnDfBrge4Mg117vv"
except Exception as e:
    st.error("🚨 서버에 비밀 키(Secrets)가 설정되지 않았습니다.")
    st.stop()

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"DB 연결 실패: {e}")
    st.stop()

def get_available_versions():
    try:
        response = supabase.table("production_plans").select("version").execute()
        if response.data:
            versions = sorted(list(set([row['version'] for row in response.data])))
            return versions
        return ["0차"]
    except:
        return ["0차"]

def fetch_production_data(version=None):
    try:
        query = supabase.table("production_plans").select("*")
        if version:
            query = query.eq("version", version)
        response = query.order("plan_date", desc=False).limit(2000).execute()
        if response.data:
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"데이터 조회 오류: {e}")
        return pd.DataFrame()

def get_monthly_total(year, month, version):
    """월간 전체 총합계 조회 (C4 셀)"""
    try:
        response = supabase.table('monthly_totals').select('*').eq('year', year).eq('month', month).eq('version', version).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]['total_quantity']
        return None
    except:
        return None

def get_line_monthly_totals(year, month, version):
    """라인별 월 총생산량 조회 (E5:E7 셀)"""
    try:
        response = supabase.table('line_monthly_totals').select('*').eq('year', year).eq('month', month).eq('version', version).execute()
        if response.data:
            return {row['line_number']: row['monthly_total'] for row in response.data}
        return {}
    except:
        return {}

def get_analysis_context(year=2025, month=8, version=None):
    context = {
        'warnings': [],
        'holiday_violations': [],
        'product_rankings': [],
        'holiday_count': 0,
        'capa_info': [],
        'daily_stats': [],
        'monthly_total': None,
        'line_monthly_totals': {}
    }
    
    try:
        # 월간 전체 총합계 (C4)
        monthly_total = get_monthly_total(year, month, version)
        if monthly_total:
            context['monthly_total'] = monthly_total
        
        # 라인별 월 총생산량 (E5:E7)
        line_totals = get_line_monthly_totals(year, month, version)
        if line_totals:
            context['line_monthly_totals'] = line_totals
        
        capa_query = supabase.table('line_capacities').select('*').eq('year', year).eq('month', month)
        if version:
            capa_query = capa_query.eq('version', version)
        capa_response = capa_query.execute()
        
        capa_dict = {}
        if capa_response.data:
            for row in capa_response.data:
                capa_dict[row['line_number']] = row['daily_capacity']
                context['capa_info'].append(f"조립{row['line_number']}라인: {row['daily_capacity']}대/일")
        
        daily_query = supabase.table('daily_line_stats').select('*').eq('year', year).eq('month', month)
        if version:
            daily_query = daily_query.eq('version', version)
        daily_stats_response = daily_query.execute()
        
        if daily_stats_response.data:
            for stat in daily_stats_response.data:
                line_num = stat['line_number']
                quantity = stat['total_quantity']
                date_str = stat['date']
                context['daily_stats'].append(f"{date_str} 조립{line_num}라인: {quantity:.0f}대")
                if line_num in capa_dict:
                    capa = capa_dict[line_num]
                    usage_rate = (quantity / capa * 100) if capa > 0 else 0
                    if quantity > capa * 0.9:
                        context['warnings'].append(
                            f"⚠️ {date_str} 조립{line_num}라인: {quantity:.0f}대 (Capa {capa}대의 {usage_rate:.1f}%)"
                        )
        
        cal_query = supabase.table('work_calendar').select('*').eq('year', year).eq('month', month)
        if version:
            cal_query = cal_query.eq('version', version)
        calendar_response = cal_query.execute()
        
        holiday_dates = set()
        if calendar_response.data:
            for day in calendar_response.data:
                if not day['is_workday']:
                    holiday_dates.add(day['date'])
            context['holiday_count'] = len(holiday_dates)
        
        if daily_stats_response.data:
            for stat in daily_stats_response.data:
                if stat['date'] in holiday_dates and stat['total_quantity'] > 0:
                    context['holiday_violations'].append(
                        f"🚫 {stat['date']} (휴무일): 조립{stat['line_number']}라인 {stat['total_quantity']:.0f}대 계획됨"
                    )
        
        product_query = supabase.table('product_summaries').select('*').eq('year', year).eq('month', month)
        if version:
            product_query = product_query.eq('version', version)
        product_response = product_query.order('monthly_total', desc=True).limit(10).execute()
        
        if product_response.data:
            for idx, product in enumerate(product_response.data, 1):
                context['product_rankings'].append(
                    f"{idx}위: {product['product_name']} ({product['monthly_total']:.0f}대)"
                )
                
    except Exception as e:
        st.warning(f"분석 데이터 조회 중 오류: {e}")
    
    return context

def compare_versions(base_version, compare_version):
    df_base = fetch_production_data(base_version)
    df_compare = fetch_production_data(compare_version)
    
    if df_base.empty or df_compare.empty:
        return "⚠️ 비교할 데이터가 부족합니다."
    
    result = f"## 📊 {base_version} → {compare_version} 변경 분석\n\n"
    
    # ========== 1. 월간 전체 총합계 비교 (C4 셀) ==========
    base_total = get_monthly_total(2025, 8, base_version)
    compare_total = get_monthly_total(2025, 8, compare_version)
    
    if base_total and compare_total:
        diff = compare_total - base_total
        diff_rate = (diff / base_total * 100) if base_total > 0 else 0
        
        result += "### 📊 월간 전체 총합계 (C4 셀 기준):\n\n"
        result += f"- **{base_version}**: {base_total:,}대\n"
        result += f"- **{compare_version}**: {compare_total:,}대\n"
        result += f"- **변화량**: {diff:+,}대 ({diff_rate:+.1f}%)\n\n"
        
        if diff < 0:
            result += f"✅ 전체 생산량이 **{abs(diff):,}대 감소**했습니다.\n\n"
        elif diff > 0:
            result += f"📈 전체 생산량이 **{diff:,}대 증가**했습니다.\n\n"
        else:
            result += "➡️ 전체 생산량은 동일합니다.\n\n"
    
    # ========== 2. 라인별 월 총생산량 비교 (E5:E7 셀) ==========
    base_line_totals = get_line_monthly_totals(2025, 8, base_version)
    compare_line_totals = get_line_monthly_totals(2025, 8, compare_version)
    
    if base_line_totals or compare_line_totals:
        result += "### 🏭 라인별 월 총생산량 (E5:E7 셀 기준):\n\n"
        
        all_lines = set(base_line_totals.keys()) | set(compare_line_totals.keys())
        
        for line_num in sorted(all_lines):
            base_qty = base_line_totals.get(line_num, 0)
            compare_qty = compare_line_totals.get(line_num, 0)
            diff = compare_qty - base_qty
            
            if diff != 0:
                emoji = "📈" if diff > 0 else "📉"
                result += f"{emoji} **조립{line_num}라인**: {base_qty:,}대 → {compare_qty:,}대 ({diff:+,}대)\n"
            else:
                result += f"➡️ **조립{line_num}라인**: {base_qty:,}대 (변동 없음)\n"
        
        result += "\n"
    
    # ========== 3. 제품별 수량 비교 ==========
    base_summary = df_base.groupby('product_name')['quantity'].sum()
    compare_summary = df_compare.groupby('product_name')['quantity'].sum()
    
    all_products = set(base_summary.index) | set(compare_summary.index)
    changes = []
    
    for product in all_products:
        base_qty = base_summary.get(product, 0)
        compare_qty = compare_summary.get(product, 0)
        diff = compare_qty - base_qty
        if diff != 0:
            changes.append({
                'product': product,
                'diff': diff,
                'base': base_qty,
                'compare': compare_qty
            })
    
    changes.sort(key=lambda x: abs(x['diff']), reverse=True)
    
    if changes:
        result += "### 🔄 제품별 수량 변경 (상위 10개):\n\n"
        for item in changes[:10]:
            emoji = "📈" if item['diff'] > 0 else "📉"
            result += f"{emoji} **{item['product']}**: "
            result += f"{int(item['base'])}대 → {int(item['compare'])}대 "
            result += f"({item['diff']:+.0f}대)\n"
    
    # ========== 4. 일별 생산량 변경 (참고용) ==========
    base_daily = df_base.groupby('plan_date')['quantity'].sum()
    compare_daily = df_compare.groupby('plan_date')['quantity'].sum()
    
    result += "\n### 📅 일별 생산량 변경 (상위 5일, 참고용):\n\n"
    
    all_dates = set(base_daily.index) | set(compare_daily.index)
    daily_changes = []
    
    for date in all_dates:
        base_qty = base_daily.get(date, 0)
        compare_qty = compare_daily.get(date, 0)
        diff = compare_qty - base_qty
        if diff != 0:
            daily_changes.append({
                'date': date,
                'diff': diff,
                'base': base_qty,
                'compare': compare_qty
            })
    
    daily_changes.sort(key=lambda x: abs(x['diff']), reverse=True)
    
    for item in daily_changes[:5]:
        emoji = "📈" if item['diff'] > 0 else "📉"
        result += f"{emoji} {item['date']}: {int(item['base'])}대 → {int(item['compare'])}대 ({item['diff']:+.0f}대)\n"
    
    result += "\n**⚠️ 중요**: 특정 날짜의 생산량 변화는 주말 배분 조정 등의 이유일 수 있으며, 생산 중단을 의미하지 않습니다. 전체 생산량은 위의 C4 셀과 E5:E7 셀 기준으로 판단해주세요.\n"
    
    return result

def ask_ai(query, df, base_version=None, compare_version=None):
    url = "https://ai.potens.ai/api/chat"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer Bx5TQFcgJW76I3kmTnDfBrge4Mg117vv"
    }
    
    current_version = compare_version or base_version
    
    if not df.empty:
        data_summary = df.groupby(['plan_date', 'line', 'product_name'])['quantity'].sum().reset_index()
        data_context = data_summary.head(50).to_string(index=False)
    else:
        data_context = "데이터 없음"
    
    comparison_text = ""
    if base_version and compare_version and base_version != compare_version:
        try:
            comparison_text = compare_versions(base_version, compare_version)
        except Exception as e:
            comparison_text = f"⚠️ 비교 중 오류: {e}"
    
    try:
        analysis = get_analysis_context(2025, 8, current_version)
        
        # 월간 전체 총합계 (C4)
        total_text = ""
        if analysis['monthly_total']:
            total_text = f"\n### 📊 월간 전체 총합계 (C4 셀):\n- {current_version}: {analysis['monthly_total']:,}대\n"
        
        # 라인별 월 총생산량 (E5:E7)
        line_totals_text = ""
        if analysis['line_monthly_totals']:
            line_totals_text = "\n### 🏭 라인별 월 총생산량 (E5:E7 셀):\n"
            for line_num in sorted(analysis['line_monthly_totals'].keys()):
                qty = analysis['line_monthly_totals'][line_num]
                line_totals_text += f"- 조립{line_num}라인: {qty:,}대\n"
        
        capa_text = "\n### 🏭 라인별 생산능력 (Capa):\n"
        if analysis['capa_info']:
            for info in analysis['capa_info']:
                capa_text += f"- {info}\n"
        
        capa_warning = ""
        if analysis['warnings']:
            capa_warning = "\n### ⚠️ Capa 초과 경고:\n"
            for warning in analysis['warnings'][:10]:
                capa_warning += f"- {warning}\n"
        else:
            capa_warning = "\n### ✅ Capa 상태: 모든 라인 정상 범위 내\n"
        
        holiday_text = ""
        if analysis['holiday_violations']:
            holiday_text = "\n### 🚫 휴무일 생산 계획:\n"
            for violation in analysis['holiday_violations'][:10]:
                holiday_text += f"- {violation}\n"
        else:
            holiday_text = f"\n### ✅ 휴무일 ({analysis['holiday_count']}일): 위반 없음\n"
        
        ranking_text = "\n### 📊 생산량 상위 제품:\n"
        for rank in analysis['product_rankings'][:10]:
            ranking_text += f"- {rank}\n"
        
        daily_text = "\n### 📅 일별 라인별 생산 통계 (샘플, 참고용):\n"
        for stat in analysis['daily_stats'][:15]:
            daily_text += f"- {stat}\n"
        
    except Exception as e:
        total_text = ""
        line_totals_text = ""
        capa_text = f"⚠️ 분석 오류: {e}"
        capa_warning = ""
        holiday_text = ""
        ranking_text = ""
        daily_text = ""
    
    system_prompt = f"""당신은 생산계획 분석 전문가입니다.

[현재 조회 버전]: {current_version or '전체'}

{total_text}

{line_totals_text}

{comparison_text}

{capa_text}

{capa_warning}

{holiday_text}

{ranking_text}

{daily_text}

[생산계획 데이터 샘플]:
{data_context}

---

**[중요: 데이터 해석 규칙]**

1. **생산량 비교 시 반드시 C4 셀과 E5:E7 셀 값을 최우선으로 사용하세요.**
   - C4 셀: 월간 전체 총합계 (모든 라인의 합)
   - E5 셀: 1라인 월 총생산량
   - E6 셀: 2라인 월 총생산량
   - E7 셀: 3라인 월 총생산량

2. **날짜별 데이터는 참고용입니다. 특정 날짜에 생산량이 0이거나 변동이 있어도 "생산 중단"이라고 판단하지 마세요.**
   - 주말 배분 조정, 근무일 변경 등의 이유일 수 있습니다.
   - 라인의 생산 여부는 E5:E7 셀의 월 총생산량으로만 판단하세요.

3. **차수 비교 시:**
   - "전체 생산량이 줄었니?" → C4 셀 값을 비교
   - "2라인 생산량이 줄었니?" → E6 셀 값을 비교
   - 날짜별 합산값이 아닌, 엑셀에 이미 계산된 합계 셀을 신뢰하세요.

4. **답변 시 반드시 구체적인 수치를 제시하세요.**
   - "0차: 217,625대 → 1차: 197,590대 (20,035대 감소)"처럼 명확하게 표현

위 규칙을 바탕으로 사용자의 질문에 정확하게 답변해주세요.
"""
    
    payload = {
        "prompt": f"{system_prompt}\n\n[사용자 질문]: {query}"
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            return response.json().get('message', '응답 없음')
        else:
            return f"⚠️ API 오류 (코드: {response.status_code})\n응답: {response.text}"
    except Exception as e:
        return f"⚠️ 통신 오류: {str(e)}"

st.title("🏭 생산계획 AI 관제 센터")

with st.sidebar:
    st.header("⚙️ 버전 설정")
    versions = get_available_versions()
    st.subheader("📌 조회할 버전")
    selected_version = st.selectbox(
        "현재 보고 있는 버전:",
        versions,
        index=len(versions)-1 if versions else 0
    )
    
    st.subheader("🔄 비교 분석")
    enable_compare = st.checkbox("버전 비교 모드")
    
    base_version = None
    if enable_compare:
        base_version = st.selectbox(
            "기준 버전:",
            versions,
            index=0
        )
        if base_version == selected_version:
            st.warning("⚠️ 같은 버전은 비교할 수 없어요")
            enable_compare = False

df_data = fetch_production_data(selected_version)

col1, col2 = st.columns([1.5, 1])

with col1:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": f"안녕하세요! 현재 **{selected_version}** 데이터를 보고 있어요. 무엇을 도와드릴까요?"}
        ]
    
    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])
    
    if prompt := st.chat_input("질문하세요"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        if enable_compare and base_version:
            ans = ask_ai(prompt, df_data, base_version, selected_version)
        else:
            ans = ask_ai(prompt, df_data, None, selected_version)
        
        st.session_state.messages.append({"role": "assistant", "content": ans})
        st.rerun()

with col2:
    st.subheader(f"📊 데이터 미리보기")
    
    if not df_data.empty:
        st.metric("총 레코드 수", len(df_data))
        
        # 월간 전체 총합계 (C4)
        monthly_total = get_monthly_total(2025, 8, selected_version)
        if monthly_total:
            st.metric("월간 전체 총합계 (C4)", f"{monthly_total:,}대")
        
        # 라인별 월 총생산량 (E5:E7)
        line_totals = get_line_monthly_totals(2025, 8, selected_version)
        if line_totals:
            st.write("**라인별 월 총생산량 (E5:E7)**")
            for line_num in sorted(line_totals.keys()):
                st.write(f"- {line_num}라인: {line_totals[line_num]:,}대")
        
        st.dataframe(df_data.head(20), use_container_width=True)
    else:
        st.info("데이터가 없습니다.")
