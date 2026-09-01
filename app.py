from PIL import Image
import requests
import streamlit as st
import base64
import io

st.set_page_config(page_title="屋根コケ診断AI")
st.title("🏠 屋根コケ診断AI")

# EC2のFastAPIサーバー
EC2_IP = "32.237.56.147"
API_URL = f"http://{EC2_IP}:8000/predict"

uploaded = st.file_uploader(
    "画像を選択してください",
    type=["jpg", "jpeg", "png"]
)

if uploaded:

    image = Image.open(uploaded).convert("RGB")

    st.subheader("元画像")
    st.image(
        image,
        use_container_width=True
    )

    if st.button("AI診断開始"):

        with st.spinner("AI解析中..."):

            files = {
                "file": (
                    uploaded.name,
                    uploaded.getvalue(),
                    uploaded.type
                )
            }

            try:

                response = requests.post(
                    API_URL,
                    files=files,
                    timeout=60
                )

                if response.status_code == 200:

                    result = response.json()

                    st.success("解析が完了しました！")

                    # =========================
                    # 診断結果
                    # =========================

                    col1, col2 = st.columns(2)

                    col1.metric(
                        "コケ率",
                        f"{result['moss_ratio']}%"
                    )

                    col2.metric(
                        "スコア",
                        f"{result['score']}点"
                    )

                    st.subheader(
                        f"ランク：{result['rank']}"
                    )

                    st.info(
                        f"**診断コメント:** "
                        f"{result['comment']}"
                    )

                    # =========================
                    # AIマスク表示
                    # =========================

                    if "mask_image" in result:

                        mask_data = result["mask_image"]

                        # data:image/png;base64,... を除去
                        if "," in mask_data:
                            mask_data = mask_data.split(
                                ",",
                                1
                            )[1]

                        mask_bytes = base64.b64decode(
                            mask_data
                        )

                        mask_image = Image.open(
                            io.BytesIO(mask_bytes)
                        )

                        st.subheader(
                            "AI検出マスク"
                        )

                        st.image(
                            mask_image,
                            caption="AIがコケと判定した領域",
                            use_container_width=True
                        )

                        # =========================
                        # 元画像＋マスクを横並び
                        # =========================

                        st.subheader(
                            "元画像とAIマスクの比較"
                        )

                        col1, col2 = st.columns(2)

                        with col1:
                            st.image(
                                image,
                                caption="元画像",
                                use_container_width=True
                            )

                        with col2:
                            st.image(
                                mask_image,
                                caption="AIマスク",
                                use_container_width=True
                            )

                else:

                    st.error(
                        f"APIエラー："
                        f"{response.status_code}\n\n"
                        f"{response.text}"
                    )

            except requests.exceptions.RequestException as e:

                st.error(
                    "サーバーに接続できませんでした。\n"
                    f"IPアドレス（{EC2_IP}）や"
                    f"8000番ポートを確認してください。\n\n"
                    f"詳細: {e}"
                )