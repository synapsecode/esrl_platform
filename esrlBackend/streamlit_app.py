import requests
import streamlit as st

st.set_page_config(page_title="ESRL Demo", layout="wide")

st.title("ESRL Demo UI")

backend_url = st.sidebar.text_input(
    "Backend URL",
    value="http://localhost:8000",
    help="FastAPI base URL",
)

st.divider()


def render_notes(payload: dict) -> None:
    if not isinstance(payload, dict):
        st.write(payload)
        return

    if payload.get("notes"):
        st.markdown("**Notes**")
        st.write(payload.get("notes"))
        return

    flashcards = payload.get("flashcards") or []
    cheat_sheet = payload.get("cheat_sheet") or ""
    mcqs = payload.get("mcqs") or []
    interview_questions = payload.get("interview_questions") or []

    if flashcards:
        with st.expander("Flashcards", expanded=True):
            for idx, card in enumerate(flashcards, start=1):
                question = card.get("question", "")
                answer = card.get("answer", "")
                st.markdown(f"**{idx}. {question}**")
                st.write(answer)

    if cheat_sheet:
        with st.expander("Cheat Sheet", expanded=True):
            st.markdown(cheat_sheet)

    if mcqs:
        with st.expander("MCQs", expanded=True):
            for idx, mcq in enumerate(mcqs, start=1):
                question = mcq.get("question", "")
                options = mcq.get("options") or []
                answer = mcq.get("answer", "")
                st.markdown(f"**{idx}. {question}**")
                for opt in options:
                    st.markdown(f"- {opt}")
                if answer:
                    st.markdown(f"**Answer:** {answer}")

    if interview_questions:
        with st.expander("Interview Questions", expanded=True):
            for idx, question in enumerate(interview_questions, start=1):
                st.markdown(f"{idx}. {question}")


def render_summary(payload: dict) -> None:
    if not isinstance(payload, dict):
        st.write(payload)
        return

    summary = payload.get("summary") or ""
    if summary:
        st.markdown("**Summary**")
        st.markdown(summary)
    else:
        st.info("No summary returned.")

with st.expander("Upload PDF", expanded=True):
    pdf_file = st.file_uploader("Choose a PDF", type=["pdf"])
    if st.button("Process PDF", type="primary"):
        if pdf_file is None:
            st.warning("Please upload a PDF first.")
        else:
            with st.spinner("Uploading and processing..."):
                try:
                    response = requests.post(
                        f"{backend_url}/upload_pdf",
                        files={"file": (pdf_file.name, pdf_file, "application/pdf")},
                        timeout=300,
                    )
                    response.raise_for_status()
                    st.success("PDF processed successfully.")
                    st.json(response.json())
                except requests.RequestException as exc:
                    st.error(f"Request failed: {exc}")

st.divider()

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("RAG Query")
    rag_query = st.text_input("Question", placeholder="Ask about the uploaded PDF")
    if st.button("Ask"):
        if not rag_query.strip():
            st.warning("Enter a question.")
        else:
            with st.spinner("Generating answer..."):
                try:
                    response = requests.post(
                        f"{backend_url}/rag",
                        json={"query": rag_query},
                        timeout=120,
                    )
                    response.raise_for_status()
                    payload = response.json()
                    st.markdown("**Answer**")
                    st.write(payload.get("answer", ""))
                    context = payload.get("context", {})
                    documents = (context.get("documents") or [[]])[0]
                    metadatas = (context.get("metadatas") or [[]])[0]
                    distances = (context.get("distances") or [[]])[0]

                    sources = []
                    images = []
                    for doc, meta, distance in zip(documents, metadatas, distances):
                        meta = meta or {}
                        if meta.get("type") == "image" and meta.get("path"):
                            images.append((meta, doc, distance))
                        else:
                            sources.append((meta, doc, distance))

                    if sources:
                        st.markdown("**Sources**")
                        for meta, doc, distance in sources:
                            heading = meta.get("heading") or "Source"
                            page = meta.get("page")
                            discourse = meta.get("discourse_type") or "unknown"
                            suffix = f" (page {page}, {discourse})" if page is not None else ""
                            st.markdown(f"- {heading}{suffix}: {doc}")

                    if images:
                        st.markdown("**Images**")
                        for meta, doc, _distance in images:
                            caption = doc or "Image"
                            st.image(meta["path"], caption=caption)

                    extra_images = payload.get("images", [])
                    if extra_images:
                        st.markdown("**Related Images**")
                        for image in extra_images:
                            if image.get("path"):
                                st.image(image["path"], caption=image.get("caption") or "Image")
                                if image.get("context") or image.get("ocr"):
                                    with st.expander("Image context"):
                                        if image.get("context"):
                                            st.markdown("**Nearby text**")
                                            st.write(image.get("context"))
                                        if image.get("ocr"):
                                            st.markdown("**OCR**")
                                            st.write(image.get("ocr"))

                    with st.expander("Raw context"):
                        st.json(context)
                except requests.RequestException as exc:
                    st.error(f"Request failed: {exc}")

with col_right:
    st.subheader("Quick Notes")
    notes_text = st.text_area("Text", height=200)
    notes_col, summary_col = st.columns(2)
    with notes_col:
        if st.button("Generate Notes"):
            if not notes_text.strip():
                st.info("Using the most recently uploaded PDF.")
            with st.spinner("Generating notes..."):
                try:
                    response = requests.post(
                        f"{backend_url}/notes",
                        json={"text": notes_text},
                        timeout=120,
                    )
                    response.raise_for_status()
                    payload = response.json()
                    render_notes(payload)
                    with st.expander("Raw response"):
                        st.json(payload)
                except requests.RequestException as exc:
                    st.error(f"Request failed: {exc}")
    with summary_col:
        if st.button("Summarize Notes"):
            if not notes_text.strip():
                st.info("Using the most recently uploaded PDF.")
            with st.spinner("Summarizing notes..."):
                try:
                    response = requests.post(
                        f"{backend_url}/notes/summary",
                        json={"text": notes_text},
                        timeout=120,
                    )
                    response.raise_for_status()
                    payload = response.json()
                    render_summary(payload)
                    with st.expander("Raw response"):
                        st.json(payload)
                except requests.RequestException as exc:
                    st.error(f"Request failed: {exc}")
