import streamlit as st
import google.generativeai as genai
import json
import typing_extensions as typing

# --- 1. 出力データの構造定義 (翻訳を追加！) ---
class TOEICQuestion(typing.TypedDict):
    question: str
    translation: str  # ← 新機能：問題文の和訳
    options: list
    correct: str
    category: str
    explanation: str

# --- 2. セッション状態（データベース）の初期化 ---
if 'weakness_db' not in st.session_state:
    st.session_state.weakness_db = {
        "品詞問題 (Parts of Speech)": 0,
        "動詞の時制・語形 (Tense/Verb Forms)": 0,
        "前置詞・接続詞 (Prepositions/Conjunctions)": 0,
        "代名詞・関係詞 (Pronouns/Relatives)": 0,
        "語彙・意味論 (Vocabulary)": 0
    }
if 'current_question' not in st.session_state:
    st.session_state.current_question = None
if 'answered' not in st.session_state:
    st.session_state.answered = False

# --- 3. 画面レイアウトの設定 ---
st.set_page_config(page_title="TOEIC AI Coach", layout="centered")
st.title("⚡ 実装版: TOEIC AI アダプティブ・コーチ")
st.write("完全リアルタイムであなたの弱点を突く問題を無限生成します。")

# --- 4. サイドバー設定 ---
st.sidebar.header("🔑 初期設定")
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    api_key = st.sidebar.text_input("Gemini API Keyを入力してください:", type="password")

st.sidebar.divider()
st.sidebar.header("📊 あなたの弱点分析データ")
for cat, score in st.session_state.weakness_db.items():
    st.sidebar.metric(label=cat, value=f"{score} エラー")

# --- 5. Gemini API呼び出し関数（高速化プロンプト導入！） ---
def generate_question_from_gemini(api_key, weakness_report):
    if not api_key:
        return None
    
    try:
        genai.configure(api_key=api_key)
        weakest_category = max(weakness_report, key=weakness_report.get)
        
        if weakness_report[weakest_category] == 0:
            focus_prompt = "TOEIC Part 5の標準的な問題をランダムなカテゴリで1問作成してください。"
        else:
            focus_prompt = f"ユーザーは現在「{weakest_category}」を苦手としています。この分野の高品質なPart 5の穴埋め問題を1問作成してください。"

        # 高速化のため、AIへの指示を「極めて簡潔に」制限しています
        prompt = f'''
        あなたは世界最高峰のTOEIC満点英語コーチです。
        以下の弱点データを分析し、Part 5（短文穴埋め問題）を1問だけ作成してください。
        {json.dumps(weakness_report, ensure_ascii=False)}
        
        【出題方針】: {focus_prompt}
        
        【指定カテゴリ】（必ず以下の5つのいずれか）
        - 品詞問題 (Parts of Speech)
        - 動詞の時制・語形 (Tense/Verb Forms)
        - 前置詞・接続詞 (Prepositions/Conjunctions)
        - 代名詞・関係詞 (Pronouns/Relatives)
        - 語彙・意味論 (Vocabulary)

        【厳格なルール（高速化対応）】
        1. optionsには4つの選択肢を格納。
        2. correctには正解の文字列を完全に一致させて格納。
        3. translationには、問題文(question)の自然な日本語訳を格納。
        4. explanationには、正解の理由と誤答の理由を「150文字以内で、極めて簡潔に」記述してください。
        '''
        
        model = genai.GenerativeModel('gemini-2.5-pro')
        
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=TOEICQuestion,
                temperature=0.7
            )
        )
        return json.loads(response.text)
        
    except Exception as e:
        st.error(f"❌ Gemini APIとの通信エラー: {e}")
        return None

# --- 6. メインアプリケーションロジック ---
if not api_key:
    st.warning("⚠️ サイドバーに「Gemini API Key」を入力すると起動します。")
else:
    if st.session_state.current_question is None:
        with st.spinner("🤖 AIが超高速で問題を生成中..."):
            st.session_state.current_question = generate_question_from_gemini(api_key, st.session_state.weakness_db)
            st.session_state.answered = False

    q = st.session_state.current_question

    if q:
        st.subheader("📚 AI厳選問題 (Part 5)")
        st.markdown(f"**🎯 ターゲット:** `{q['category']}`")
        st.info(f"**Question:**\n\n{q['question']}")
        
        user_choice = st.radio("最も適切なものを1つ選んでください:", q['options'], index=None, key="toeic_radio")
        submit_clicked = st.button("📝 回答を送信して解説を見る")
        
        if submit_clicked and not st.session_state.answered:
            if user_choice:
                st.session_state.answered = True
                st.divider()
                
                # 正誤判定
                if user_choice == q['correct']:
                    st.success("🎉 **正解です！**")
                    st.balloons()
                    if st.session_state.weakness_db[q['category']] > 0:
                        st.session_state.weakness_db[q['category']] -= 1
                else:
                    st.error(f"❌ **不正解... 正解は「 {q['correct']} 」です。**")
                    st.session_state.weakness_db[q['category']] += 1
                
                # 和訳と解説の表示（新機能！）
                st.markdown("### 📖 問題文の和訳")
                st.write(f"> {q['translation']}")
                
                st.markdown("### 🤖 スピード解説")
                st.write(q['explanation'])
                
                st.sidebar.caption("データ更新完了 🔄")
            else:
                st.warning("選択肢を1つ選んでから送信してください。")

        # 次へ進むボタン
        if st.session_state.answered:
            st.divider()
            if st.button("⏭️ 次の問題へ進む（高速ロード）"):
                st.session_state.current_question = None
                st.session_state.answered = False
                st.rerun()
