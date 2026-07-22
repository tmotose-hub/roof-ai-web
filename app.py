import streamlit as st
import requests
from PIL import Image

st.set_page_config(page_title="屋根コケ診断AI")
st.title("🏠 屋根コケ診断AI")

uploaded = st.file_uploader("画像を選択してください", type=["jpg", "jpeg", "png"])

if uploaded:
    image = Image.open(uploaded)
    st.image(image, use_container_width=True)

    if st.button("AI診断開始"):
        with st.spinner("AI解析中..."):
            # ここを修正！(ファイル名, データ, ファイル形式 の形式で渡す)
            files = {
                "file": (uploaded.name, uploaded.getvalue(), uploaded.type)
            }
            
            # FastAPIに画像を送信
            response = requests.post("https://roof-ai-5-demo.onrender.com/predict", files=files)
            
            # 結果を表示
            if response.status_code == 200:
                result = response.json()
                st.metric("コケ率", f"{result['moss_ratio']}%")
                st.metric("スコア", f"{result['score']}")
                st.subheader(f"ランク：{result['rank']}")
            else:
                st.error("エラーが発生しました。FastAPIサーバーが起動しているか確認してください。")