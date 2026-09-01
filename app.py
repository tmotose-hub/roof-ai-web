from PIL import Image, ImageOps
import requests
import streamlit as st
import base64
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image as RLImage,
    Table,
    TableStyle,
    PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

st.set_page_config(page_title="屋根コケ診断AI")
st.title("🏠 屋根コケ診断AI")

# EC2のFastAPIサーバー
EC2_IP = "32.237.56.147"
API_URL = f"http://{EC2_IP}:8000/predict"

# 日本語フォント登録（環境にIPAexフォント等がある場合のみ有効）
# 無ければ標準フォントにフォールバックする
JP_FONT_NAME = "Helvetica"
try:
    pdfmetrics.registerFont(
        TTFont("IPAexGothic", "ipaexg.ttf")
    )
    JP_FONT_NAME = "IPAexGothic"
except Exception:
    pass


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


def pil_to_rl_image(pil_image, max_width_mm=80):
    """PIL画像をreportlab用のImageフローアブルに変換"""

    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    buf.seek(0)

    w, h = pil_image.size
    max_width = max_width_mm * mm
    scale = max_width / w
    display_w = max_width
    display_h = h * scale

    return RLImage(buf, width=display_w, height=display_h)


def build_pdf_report(results):
    """
    results: [
        {
            "filename": str,
            "moss_ratio": float,
            "score": float,
            "rank": str,
            "comment": str,
            "original_image": PIL.Image,
            "overlay_image": PIL.Image,
        },
        ...
    ]
    を受け取り、PDFのバイト列を返す。
    """

    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleJP",
        parent=styles["Title"],
        fontName=JP_FONT_NAME
    )
    heading_style = ParagraphStyle(
        "HeadingJP",
        parent=styles["Heading2"],
        fontName=JP_FONT_NAME
    )
    normal_style = ParagraphStyle(
        "NormalJP",
        parent=styles["Normal"],
        fontName=JP_FONT_NAME,
        fontSize=10,
        leading=14
    )

    story = []

    # 表紙
    story.append(
        Paragraph("屋根コケ点検レポート", title_style)
    )
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            f"作成日時: "
            f"{datetime.now().strftime('%Y年%m月%d日 %H:%M')}",
            normal_style
        )
    )
    story.append(
        Paragraph(
            f"対象画像数: {len(results)}枚",
            normal_style
        )
    )
    story.append(Spacer(1, 12))

    for i, r in enumerate(results):

        story.append(
            Paragraph(f"■ {r['filename']}", heading_style)
        )
        story.append(Spacer(1, 4))

        # 診断結果テーブル
        table_data = [
            ["コケ率", f"{r['moss_ratio']}%"],
            ["スコア", f"{r['score']}点"],
            ["ランク", r["rank"]],
            ["診断コメント", r["comment"]],
        ]

        table = Table(
            table_data,
            colWidths=[35 * mm, 130 * mm]
        )
        table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), JP_FONT_NAME),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(table)
        story.append(Spacer(1, 8))

        # 元画像／オーバーレイ画像を横に並べる
        img_table = Table(
            [[
                pil_to_rl_image(r["original_image"]),
                pil_to_rl_image(r["overlay_image"])
            ]],
            colWidths=[85 * mm, 85 * mm]
        )
        img_table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ])
        )
        story.append(img_table)

        caption_table = Table(
            [["元画像", "元画像＋AIマスク（オーバーレイ）"]],
            colWidths=[85 * mm, 85 * mm]
        )
        caption_table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), JP_FONT_NAME),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.grey),
            ])
        )
        story.append(caption_table)

        if i != len(results) - 1:
            story.append(PageBreak())

    doc.build(story)

    buf.seek(0)
    return buf.getvalue()


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

        # PDFレポート用に結果を貯めておく
        all_results = []

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

                        overlay_image = image

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

                        # PDF出力用に結果を保存
                        all_results.append({
                            "filename": uploaded.name,
                            "moss_ratio": result["moss_ratio"],
                            "score": result["score"],
                            "rank": result["rank"],
                            "comment": result["comment"],
                            "original_image": image,
                            "overlay_image": overlay_image,
                        })

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

        # =========================
        # PDFレポート出力
        # =========================

        if all_results:

            st.divider()
            st.subheader("📄 点検結果レポート")

            pdf_bytes = build_pdf_report(all_results)

            st.download_button(
                label="PDFレポートをダウンロード",
                data=pdf_bytes,
                file_name=(
                    "roof_inspection_report_"
                    f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                ),
                mime="application/pdf"
            )