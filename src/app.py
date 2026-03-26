"""
app.py
Gradio UI 진입점.

실행 방법:
    python src/app.py
또는:
    gradio src/app.py
"""

from dotenv import load_dotenv
load_dotenv()  # .env 파일에서 API 키 로드

import gradio as gr
from src.recommender import recommend


def chat_process(message, history, foot, usage, price_val):
    return recommend(message, history, foot, usage, price_val)


# ─────────────────────────────────────────
# UI 레이아웃
# ─────────────────────────────────────────

with gr.Blocks(theme=gr.themes.Soft()) as app:
    gr.Markdown("""
# 🏃‍♂️ AI 러닝화 큐레이터
사용자의 발 타입, 용도, 예산을 기반으로 러닝화를 추천합니다.
""")

    with gr.Row():
        # ── 왼쪽: 필터 ──
        with gr.Column(scale=1):
            gr.Markdown("### 🔍 필터")

            foot_type = gr.CheckboxGroup(
                ["중립", "과내전", "모름"],
                label="발 타입",
            )

            def enforce_single_foot(foot_list):
                """발 타입은 하나만 선택 가능"""
                if not foot_list:
                    return []
                return [foot_list[-1]]

            foot_type.change(enforce_single_foot, foot_type, foot_type)

            usage_type = gr.CheckboxGroup(
                ["데일리런", "레이스"],
                label="사용 용도",
            )

            price_slider = gr.Slider(
                0, 540000,
                value=540000,
                step=10000,
                label="최대 예산 (원)",
            )

        # ── 오른쪽: 채팅 ──
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(label="💬 상담", type="messages")

            with gr.Row():
                msg_input = gr.Textbox(
                    placeholder="예: 무릎 안 아픈 러닝화 추천",
                    scale=8,
                )
                send_btn = gr.Button("전송", variant="primary", scale=2)

    inputs = [msg_input, chatbot, foot_type, usage_type, price_slider]
    outputs = [chatbot, msg_input]

    send_btn.click(chat_process, inputs, outputs)
    msg_input.submit(chat_process, inputs, outputs)


if __name__ == "__main__":
    app.launch(share=True)
