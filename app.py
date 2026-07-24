from PIL import Image
import requests
import streamlit as st

st.set_page_config(page_title="屋根コケ診断AI")
st.title("🏠 屋根コケ診断AI")

# 🔗 EC2のFastAPIサーバーURL（ご自身のEC2のIPアドレスに変更してください）
# 例: "http://32.237.56.147:8000/predict"
EC2_IP = "32.237.56.147"  # 👈 ここをEC2のパブリックIP（またはElastic IP）に書き換えてください
API_URL = f"http://{EC2_IP}:8000/predict"

uploaded = st.file_uploader("画像を選択してください", type=["jpg", "jpeg", "png"])

if uploaded:
    image = Image.open(uploaded)
    st.image(image, use_container_width=True)

    if st.button("AI診断開始"):
        with st.spinner("AI解析中..."):
            # ファイルデータを作成
            files = {
                "file": (uploaded.name, uploaded.getvalue(), uploaded.type)
            }

            try:
                # EC2上のFastAPIへ画像を送信
                response = requests.post(API_URL, files=files, timeout=30)

                # 結果を表示
                if response.status_code == 200:
                    result = response.json()

                    st.success("解析が完了しました！")

                    # メトリクス表示
                    col1, col2 = st.columns(2)
                    col1.metric("コケ率", f"{result['moss_ratio']}%")
                    col2.metric("スコア", f"{result['score']}点")

                    st.subheader(f"ランク：{result['rank']}")
                    st.info(f"**診断コメント:** {result['comment']}")

                else:
                    st.error(
                        f"エラーが発生しました。(ステータスコード: {response.status_code})\n"
                        "FastAPIサーバーが起動しているか確認してください。"
                    )

            except requests.exceptions.RequestException as e:
                st.error(
                    f"サーバーに接続できませんでした。\n"
                    f"IPアドレス（{EC2_IP}）やセキュリティグループ（8000番ポート）の設定を確認してください。\n"
                    f"詳細: {e}"
                )