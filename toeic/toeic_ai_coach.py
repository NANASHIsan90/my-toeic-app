import streamlit as st
import google.generativeai as genai
import json
import typing_extensions as typing

# --- 1. 出力データの構造定義 (Structured Outputs) ---
class TOEICQuestion(typing.TypedDict):
    question: str
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
st.write("Google Gemini APIと直接連携し、完全リアルタイムであなたの弱点を突く問題を無限生成します。")

# --- 4. サイドバー設定（APIキー入力＆弱点可視化） ---
st.sidebar.header("🔑 初期設定")
api_key = st.sidebar.text_input("Gemini API Keyを入力してください:", type="password", help="Google AI Studioから無料で取得したキーを入力します。")
st.sidebar.markdown("[👉 無料APIキーの取得はこちら (Google AI Studio)](https://aistudio.google.com/)")

st.sidebar.divider()
st.sidebar.header("📊 あなたの弱点分析データ")
st.sidebar.write("（ミスした分野のカウントが増え、AIがその分野を狙い撃ちします）")
for cat, score in st.session_state.weakness_db.items():
    st.sidebar.metric(label=cat, value=f"{score} エラー")

# --- 5. 本物のGemini APIを呼び出す関数 ---
def generate_question_from_gemini(api_key, weakness_report):
    if not api_key:
        st.info("💡 アプリを動かすには、サイドバーにGemini API Keyを入力してください。")
        return None
    
    try:
        # APIの初期設定
        genai.configure(api_key=api_key)
        
        # 最もエラーが多い苦手分野を特定
        weakest_category = max(weakness_report, key=weakness_report.get)
        
        if weakness_report[weakest_category] == 0:
            focus_prompt = "TOEIC Part 5の標準的な問題をランダムなカテゴリで1問作成してください。"
        else:
            focus_prompt = f"ユーザーは現在「{weakest_category}」を苦手としています。この分野の理解度を試し、克服を促すための高品質なPart 5の穴埋め問題を1問作成してください。"

        # AIへの命令文（プロンプト）の構築
        prompt = f'''
        あなたは世界最高峰のTOEIC満点英語コーチであり、一流の文法問題作成者です。
        ユーザーの弱点データを分析し、学習効果が最も高いPart 5（短文穴埋め問題）を1問だけ作成してください。
        
        【ユーザーの現在の弱点ステータス】
        {json.dumps(weakness_report, ensure_ascii=False)}
        
        【今回の出題方針】
        {focus_prompt}
        
        【指定カテゴリ】
        JSONの "category" フィールドには、必ず以下の5つのうちいずれか1つを厳密に指定してください：
        - 品詞問題 (Parts of Speech)
        - 動詞の時制・語形 (Tense/Verb Forms)
        - 前置詞・接続詞 (Prepositions/Conjunctions)
        - 代名詞・関係詞 (Pronouns/Relatives)
        - 語彙・意味論 (Vocabulary)

        【厳格なルール】
        1. optionsには4つの選択肢を格納してください。
        2. correctには、optionsの中の正解の文字列と「完全に一致する文字列」を入れてください。
        3. explanationには、なぜそれが正解なのか、他の選択肢がなぜ誤りなのかを、日本人が深く納得できるように論理的かつ分かりやすい日本語で記述してください。
        '''
        
        # モデルの呼び出し（軽量・高速・低コストな gemini-1.5-flash を採用）
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",  # JSON出力を強制
                response_schema=TOEICQuestion,          # 定義したスキーマに強制
                temperature=0.7
            )
        )
        
        # 返ってきたJSONテキストをPythonの辞書型に変換
        return json.loads(response.text)
        
    except Exception as e:
        st.error(f"❌ Gemini APIとの通信でエラーが発生しました: {e}")
        return None

# --- 6. メインアプリケーションロジック ---
if not api_key:
    st.warning("⚠️ 画面左側のサイドバーに「Gemini API Key」を入力すると、AIコーチが始動します。")
else:
    # 現在の問題がない場合、新しくAPIから取得
    if st.session_state.current_question is None:
        with st.spinner("🤖 AIコーチがあなたの弱点データを読み込み、極上の問題を作成中..."):
            st.session_state.current_question = generate_question_from_gemini(api_key, st.session_state.weakness_db)
            st.session_state.answered = False

    q = st.session_state.current_question

    if q:
        # 問題画面の描画
        st.subheader("📚 AI厳選問題 (Part 5)")
        st.markdown(f"**🎯 ターゲット分野:** `{q['category']}`")
        
        # 問題文をボックスで綺麗に表示
        st.info(f"**Question:**

{q['question']}")
        
        # 選択肢のラジオボタン（初期状態は未選択）
        user_choice = st.radio("最も適切なものを1つ選んでください:", q['options'], index=None, key="toeic_radio")
        
        # 送信ボタン
        submit_clicked = st.button("📝 回答を送信してAIの解説を見る")
        
        if submit_clicked and not st.session_state.answered:
            if user_choice:
                st.session_state.answered = True
                st.divider()
                
                # 採点と解説の表示
                if user_choice == q['correct']:
                    st.success("🎉 **正解です！その調子！**")
                    st.balloons()
                    # 正解したらその分野のペナルティを少し減らす（最低0）
                    if st.session_state.weakness_db[q['category']] > 0:
                        st.session_state.weakness_db[q['category']] -= 1
                else:
                    st.error(f"❌ **不正解... 正解は「 {q['correct']} 」です。**")
                    # 不正解ならその分野のカウントをプラス
                    st.session_state.weakness_db[q['category']] += 1
                
                # AIによる詳細解説
                st.markdown("### 🤖 専属AIコーチの熱血解説")
                st.write(q['explanation'])
                
                # サイドバーを即時更新するためのトリガー
                st.sidebar.caption("データ更新完了 🔄")
            else:
                st.warning("選択肢を1つ選んでから送信してください。")

        # 次の問題へ進むボタン（回答後に表示）
        if st.session_state.answered:
            st.divider()
            if st.button("⏭️ 次のAI生成問題へ挑む"):
                st.session_state.current_question = None
                st.session_state.answered = False
                st.rerun()
