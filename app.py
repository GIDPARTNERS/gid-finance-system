import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

# 페이지 설정
st.set_page_config(
    page_title="GID Partners - 재무 관리 시스템",
    page_icon="💼",
    layout="wide"
)

# 데이터베이스 초기화
def init_db():
    conn = sqlite3.connect('finance.db')
    c = conn.cursor()
    
    # 거래 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            category TEXT NOT NULL,
            project TEXT,
            description TEXT,
            amount REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 프로젝트 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            client TEXT,
            budget REAL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# 거래 추가
def add_transaction(trans_date, trans_type, category, project, description, amount):
    conn = sqlite3.connect('finance.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO transactions (date, type, category, project, description, amount)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (trans_date, trans_type, category, project, description, amount))
    conn.commit()
    conn.close()

# 프로젝트 추가
def add_project(name, client, budget):
    conn = sqlite3.connect('finance.db')
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO projects (name, client, budget)
            VALUES (?, ?, ?)
        ''', (name, client, budget))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# 데이터 조회
def get_transactions(start_date=None, end_date=None):
    conn = sqlite3.connect('finance.db')
    query = "SELECT * FROM transactions"
    
    if start_date and end_date:
        query += f" WHERE date BETWEEN '{start_date}' AND '{end_date}'"
    
    query += " ORDER BY date DESC"
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_projects():
    conn = sqlite3.connect('finance.db')
    df = pd.read_sql_query("SELECT * FROM projects WHERE status='active'", conn)
    conn.close()
    return df

# 재무 지표 계산
def calculate_metrics(df):
    if df.empty:
        return 0, 0, 0, 0
    
    income = df[df['type'] == '수입']['amount'].sum()
    expense = df[df['type'] == '지출']['amount'].sum()
    profit = income - expense
    profit_margin = (profit / income * 100) if income > 0 else 0
    
    return income, expense, profit, profit_margin

# 프로젝트별 수익성
def project_profitability(df):
    if df.empty:
        return pd.DataFrame()
    
    project_data = df[df['project'].notna()].groupby('project').agg({
        'amount': lambda x: x[df.loc[x.index, 'type'] == '수입'].sum() - x[df.loc[x.index, 'type'] == '지출'].sum()
    }).reset_index()
    project_data.columns = ['프로젝트', '순이익']
    
    return project_data.sort_values('순이익', ascending=False)

# 메인 앱
def main():
    init_db()
    
    # 사이드바
    st.sidebar.title("🏢 GID Partners")
    st.sidebar.markdown("### 재무 관리 시스템")
    
    menu = st.sidebar.radio(
        "메뉴",
        ["📊 대시보드", "💰 거래 관리", "📁 프로젝트 관리", "📈 리포트", "⚙️ 데이터 관리"]
    )
    
    # 날짜 필터
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📅 기간 설정")
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("시작일", date(datetime.now().year, 1, 1))
    with col2:
        end_date = st.date_input("종료일", date.today())
    
    # 데이터 로드
    df = get_transactions(start_date, end_date)
    
    # 📊 대시보드
    if menu == "📊 대시보드":
        st.title("📊 재무 대시보드")
        
        # 주요 지표
        income, expense, profit, profit_margin = calculate_metrics(df)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("💵 총 수입", f"₩{income:,.0f}")
        with col2:
            st.metric("💸 총 지출", f"₩{expense:,.0f}")
        with col3:
            st.metric("💰 순이익", f"₩{profit:,.0f}", delta=f"{profit_margin:.1f}%")
        with col4:
            st.metric("📊 이익률", f"{profit_margin:.1f}%")
        
        st.markdown("---")
        
        if not df.empty:
            # 차트 행
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📈 월별 수입/지출 추이")
                df['date'] = pd.to_datetime(df['date'])
                df['month'] = df['date'].dt.to_period('M').astype(str)
                
                monthly = df.groupby(['month', 'type'])['amount'].sum().reset_index()
                
                fig = px.bar(monthly, x='month', y='amount', color='type',
                           barmode='group',
                           color_discrete_map={'수입': '#2ecc71', '지출': '#e74c3c'},
                           labels={'amount': '금액 (원)', 'month': '월', 'type': '구분'})
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.subheader("🎯 카테고리별 지출 분포")
                expense_by_cat = df[df['type'] == '지출'].groupby('category')['amount'].sum()
                
                if not expense_by_cat.empty:
                    fig = px.pie(values=expense_by_cat.values, 
                               names=expense_by_cat.index,
                               hole=0.4)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("지출 데이터가 없습니다.")
            
            # 프로젝트 수익성
            st.markdown("---")
            st.subheader("💼 프로젝트별 수익성")
            
            proj_profit = project_profitability(df)
            
            if not proj_profit.empty:
                fig = px.bar(proj_profit, x='프로젝트', y='순이익',
                           color='순이익',
                           color_continuous_scale=['#e74c3c', '#f39c12', '#2ecc71'])
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("프로젝트 데이터가 없습니다.")
            
            # 최근 거래
            st.markdown("---")
            st.subheader("📝 최근 거래 내역 (최근 10건)")
            recent = df.head(10)[['date', 'type', 'category', 'project', 'description', 'amount']]
            recent.columns = ['날짜', '구분', '카테고리', '프로젝트', '설명', '금액']
            st.dataframe(recent, use_container_width=True)
        else:
            st.info("선택한 기간에 거래 내역이 없습니다. 거래를 추가해주세요!")
    
    # 💰 거래 관리
    elif menu == "💰 거래 관리":
        st.title("💰 거래 관리")
        
        tab1, tab2 = st.tabs(["➕ 거래 추가", "📋 거래 내역"])
        
        with tab1:
            st.subheader("새 거래 추가")
            
            col1, col2 = st.columns(2)
            
            with col1:
                trans_date = st.date_input("날짜", date.today(), key="trans_date")
                trans_type = st.selectbox("구분", ["수입", "지출"])
                
                if trans_type == "수입":
                    category = st.selectbox("카테고리", 
                        ["컨설팅 수입", "자문료", "교육/강의", "기타 수입"])
                else:
                    category = st.selectbox("카테고리",
                        ["인건비", "사무실 운영", "마케팅", "IT/소프트웨어", 
                         "교통/출장", "접대/회의", "세금/수수료", "기타 지출"])
            
            with col2:
                projects = get_projects()
                project_list = ["없음"] + projects['name'].tolist() if not projects.empty else ["없음"]
                project = st.selectbox("프로젝트", project_list)
                project = None if project == "없음" else project
                
                amount = st.number_input("금액 (원)", min_value=0, step=1000)
                description = st.text_input("설명")
            
            if st.button("💾 저장", type="primary", use_container_width=True):
                if amount > 0:
                    add_transaction(str(trans_date), trans_type, category, 
                                  project, description, amount)
                    st.success("✅ 거래가 추가되었습니다!")
                    st.rerun()
                else:
                    st.error("금액을 입력해주세요.")
        
        with tab2:
            st.subheader("거래 내역")
            
            if not df.empty:
                # 필터링
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    type_filter = st.multiselect("구분", df['type'].unique(), default=df['type'].unique())
                with col2:
                    cat_filter = st.multiselect("카테고리", df['category'].unique())
                with col3:
                    proj_filter = st.multiselect("프로젝트", df['project'].dropna().unique())
                
                filtered_df = df.copy()
                
                if type_filter:
                    filtered_df = filtered_df[filtered_df['type'].isin(type_filter)]
                if cat_filter:
                    filtered_df = filtered_df[filtered_df['category'].isin(cat_filter)]
                if proj_filter:
                    filtered_df = filtered_df[filtered_df['project'].isin(proj_filter)]
                
                st.dataframe(
                    filtered_df[['date', 'type', 'category', 'project', 'description', 'amount']],
                    column_config={
                        "date": "날짜",
                        "type": "구분",
                        "category": "카테고리",
                        "project": "프로젝트",
                        "description": "설명",
                        "amount": st.column_config.NumberColumn("금액", format="₩%.0f")
                    },
                    use_container_width=True
                )
                
                st.metric("필터된 거래 합계", f"₩{filtered_df['amount'].sum():,.0f}")
            else:
                st.info("거래 내역이 없습니다.")
    
    # 📁 프로젝트 관리
    elif menu == "📁 프로젝트 관리":
        st.title("📁 프로젝트 관리")
        
        tab1, tab2 = st.tabs(["➕ 프로젝트 추가", "📋 프로젝트 목록"])
        
        with tab1:
            st.subheader("새 프로젝트 추가")
            
            col1, col2 = st.columns(2)
            
            with col1:
                proj_name = st.text_input("프로젝트명")
                proj_client = st.text_input("클라이언트")
            
            with col2:
                proj_budget = st.number_input("예산 (원)", min_value=0, step=1000000)
            
            if st.button("💾 프로젝트 저장", type="primary", use_container_width=True):
                if proj_name:
                    if add_project(proj_name, proj_client, proj_budget):
                        st.success(f"✅ 프로젝트 '{proj_name}'이(가) 추가되었습니다!")
                        st.rerun()
                    else:
                        st.error("❌ 이미 존재하는 프로젝트명입니다.")
                else:
                    st.error("프로젝트명을 입력해주세요.")
        
        with tab2:
            projects = get_projects()
            
            if not projects.empty:
                st.subheader("활성 프로젝트")
                
                for _, proj in projects.iterrows():
                    with st.expander(f"📁 {proj['name']} - {proj['client']}"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**예산:** ₩{proj['budget']:,.0f}")
                        
                        # 프로젝트 재무 현황
                        proj_trans = df[df['project'] == proj['name']]
                        
                        if not proj_trans.empty:
                            proj_income = proj_trans[proj_trans['type'] == '수입']['amount'].sum()
                            proj_expense = proj_trans[proj_trans['type'] == '지출']['amount'].sum()
                            proj_profit = proj_income - proj_expense
                            
                            with col2:
                                st.write(f"**수입:** ₩{proj_income:,.0f}")
                                st.write(f"**지출:** ₩{proj_expense:,.0f}")
                                st.write(f"**순이익:** ₩{proj_profit:,.0f}")
                            
                            # 진행률
                            if proj['budget'] > 0:
                                progress = min(proj_income / proj['budget'], 1.0)
                                st.progress(progress)
                                st.caption(f"예산 대비 수입: {progress*100:.1f}%")
                        else:
                            st.info("거래 내역이 없습니다.")
            else:
                st.info("등록된 프로젝트가 없습니다.")
    
    # 📈 리포트
    elif menu == "📈 리포트":
        st.title("📈 재무 리포트")
        
        if not df.empty:
            # 손익계산서
            st.subheader("💼 손익계산서")
            
            income_df = df[df['type'] == '수입'].groupby('category')['amount'].sum().reset_index()
            expense_df = df[df['type'] == '지출'].groupby('category')['amount'].sum().reset_index()
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📈 수입**")
                income_df.columns = ['카테고리', '금액']
                st.dataframe(income_df, use_container_width=True, hide_index=True)
                total_income = income_df['금액'].sum()
                st.markdown(f"**총 수입: ₩{total_income:,.0f}**")
            
            with col2:
                st.markdown("**📉 지출**")
                expense_df.columns = ['카테고리', '금액']
                st.dataframe(expense_df, use_container_width=True, hide_index=True)
                total_expense = expense_df['금액'].sum()
                st.markdown(f"**총 지출: ₩{total_expense:,.0f}**")
            
            st.markdown("---")
            net_profit = total_income - total_expense
            st.markdown(f"### 💰 순이익: ₩{net_profit:,.0f}")
            
            # 월별 상세 리포트
            st.markdown("---")
            st.subheader("📅 월별 상세 리포트")
            
            df['date'] = pd.to_datetime(df['date'])
            df['month'] = df['date'].dt.to_period('M').astype(str)
            
            monthly_report = df.groupby(['month', 'type'])['amount'].sum().reset_index()
            monthly_pivot = monthly_report.pivot(index='month', columns='type', values='amount').fillna(0)
            monthly_pivot['순이익'] = monthly_pivot.get('수입', 0) - monthly_pivot.get('지출', 0)
            
            st.dataframe(
                monthly_pivot.style.format("₩{:,.0f}"),
                use_container_width=True
            )
        else:
            st.info("리포트를 생성할 데이터가 없습니다.")
    
    # ⚙️ 데이터 관리
    elif menu == "⚙️ 데이터 관리":
        st.title("⚙️ 데이터 관리")
        
        tab1, tab2 = st.tabs(["📥 Import", "📤 Export"])
        
        with tab1:
            st.subheader("엑셀 데이터 가져오기")
            st.info("엑셀 파일 형식: date, type, category, project, description, amount")
            
            uploaded_file = st.file_uploader("엑셀 파일 선택", type=['xlsx', 'xls'])
            
            if uploaded_file:
                try:
                    import_df = pd.read_excel(uploaded_file)
                    st.write("미리보기:")
                    st.dataframe(import_df.head())
                    
                    if st.button("📥 데이터 가져오기", type="primary"):
                        conn = sqlite3.connect('finance.db')
                        import_df.to_sql('transactions', conn, if_exists='append', index=False)
                        conn.close()
                        st.success(f"✅ {len(import_df)}건의 데이터를 가져왔습니다!")
                        st.rerun()
                except Exception as e:
                    st.error(f"오류: {str(e)}")
        
        with tab2:
            st.subheader("데이터 내보내기")
            
            if not df.empty:
                # Excel export
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='거래내역', index=False)
                    
                    projects = get_projects()
                    if not projects.empty:
                        projects.to_excel(writer, sheet_name='프로젝트', index=False)
                
                st.download_button(
                    label="📤 엑셀로 다운로드",
                    data=output.getvalue(),
                    file_name=f"재무데이터_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("내보낼 데이터가 없습니다.")

if __name__ == "__main__":
    main()
