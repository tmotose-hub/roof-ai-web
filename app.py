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


def diagnose_image(image_bytes, filename, content_type):
    """1枚分をAPIに送信して結果を取得する"""

    files = {
        "file": (
            filename,
            image_bytes,
            content_type
        )
    }

    response = requests.post(
        API_URL,
        files=files,
        timeout=60
    )

    return response


uploaded_files = st.file_uploader(
    "画像を選択してください（複数選択可）",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

if uploaded_files:

    st.write(f"{len(uploaded_files)}枚の画像が選択されています")

    overlay_alpha = st.slider(
        "マスクの濃さ",
        min_value=0.0,
        max_value=1.0,
        value=0.5,
        step=0.05
    )

    invert_mask = st.checkbox(
        "マスクを反転する（黒=検出領域の場合はON）",
        value=True
    )

    if st.button("AI診断開始"):

        for uploaded in uploaded_files:

            st.divider()
            st.subheader(f"📷 {uploaded.name}")

            image = Image.open(uploaded).convert("RGB")

            with st.spinner("AI解析中..."):

                try:

                    response = diagnose_image(
                        uploaded.getvalue(),
                        uploaded.name,
                        uploaded.type
                    )

                    if response.status_code == 200:

                        result = response.json()

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

                        st.write(f"**ランク：{result['rank']}**")

                        st.info(
                            f"**診断コメント:** "
                            f"{result['comment']}"
                        )

                        # =========================
                        # 元画像 と 元画像＋AIマスク の比較
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

                            overlay_image = overlay_mask_on_image(
                                image,
                                mask_image,
                                color=(255, 0, 0),
                                alpha=overlay_alpha,
                                invert=invert_mask
                            )

                            col_a, col_b = st.columns(2)

                            with col_a:
                                st.image(
                                    image,
                                    caption="元画像",
                                    use_container_width=True
                                )

                            with col_b:
                                st.image(
                                    overlay_image,
                                    caption="元画像＋AIマスク（オーバーレイ）",
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