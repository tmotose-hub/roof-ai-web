from PIL import Image, ImageOps
import requests
import streamlit as st
import base64
import io

st.set_page_config(page_title="屋根コケ診断AI")
st.title("🏠 屋根コケ診断AI")

# EC2のFastAPIサーバー
EC2_IP = "32.237.56.147"
API_URL = f"http://{EC2_IP}:8000/predict"


def overlay_mask_on_image(
    base_image,
    mask_image,
    color=(255, 0, 0),
    alpha=0.5,
    invert=True
):
    """
    元画像にマスク画像を半透明色で重ねて1枚の画像にする。

    invert=True の場合、
    「黒=検出領域（コケ）、白=背景」というマスク形式を想定し、
    反転してから色を乗せる。
    """

    base = base_image.convert("RGBA")

    mask_resized = mask_image.convert("L").resize(base.size)

    if invert:
        mask_resized = ImageOps.invert(mask_resized)

    color_layer = Image.new(
        "RGBA",
        base.size,
        color + (0,)
    )

    alpha_mask = mask_resized.point(
        lambda p: int(p * alpha)
    )
    color_layer.putalpha(alpha_mask)

    combined = Image.alpha_composite(base, color_layer)

    return combined.convert("RGB")


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
                    # 元画像にマスクを重ねて表示
                    # =========================

                    if "mask_image" in result:

                        mask_data = result["mask_image"]

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
                            "AI検出結果"
                        )

                        col_a, col_b = st.columns(2)

                        with col_a:
                            overlay_alpha = st.slider(
                                "マスクの濃さ",
                                min_value=0.0,
                                max_value=1.0,
                                value=0.5,
                                step=0.05
                            )

                        with col_b:
                            invert_mask = st.checkbox(
                                "マスクを反転する"
                                "（黒=検出領域の場合はON）",
                                value=True
                            )

                        overlay_image = overlay_mask_on_image(
                            image,
                            mask_image,
                            color=(255, 0, 0),
                            alpha=overlay_alpha,
                            invert=invert_mask
                        )

                        # =========================
                        # 元画像とオーバーレイ画像を横並び比較
                        # =========================

                        st.subheader(
                            "元画像とAI検出結果の比較"
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
                                overlay_image,
                                caption="AI検出結果（コケ領域を赤色で表示）",
                                use_container_width=True
                            )

                        # 生のマスクは折りたたみで確認用に残す
                        with st.expander("AIマスク単体を見る"):
                            st.image(
                                mask_image,
                                caption="AIマスク（生データ）",
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