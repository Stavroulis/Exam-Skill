import difflib
import html
import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from core.document_store import (
    init_storage,
    create_case,
    list_cases,
    save_uploaded_pdf,
    list_case_documents,
    get_document_text,
    pdf_dir,
    save_structured_document,
    load_structured_document,
)
from core.pdf_extract import extract_and_cache_pdf_text
from core.llm import OPENAI_MODELS, ANTHROPIC_MODELS
from core.structure import guess_document_type, structure_document
from core.document_mapper import (
    classify_filename,
    build_mapping,
    save_mapping,
    load_mapping,
    role_to_structure_type,
)
from skills.registry import SKILLS


# ============================================================
# App configuration
# ============================================================

st.set_page_config(
    page_title="Patent Matters Skill Runner",
    layout="wide",
)

init_storage()

st.title("Patent Matters — Skill Runner")


# ============================================================
# General utility functions
# ============================================================

def normalize_claim_number(value):
    """
    Convert claim numbers to int where possible.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def get_case_results_dir(case_name: str) -> Path:
    """
    Return and create the results directory for a case.
    """
    results_dir = Path("data") / "cases" / case_name / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir


def save_text_result(case_name: str, filename: str, result_text: str) -> Path:
    """
    Save a full LLM result as a text file in the case results folder.
    """
    output_path = get_case_results_dir(case_name) / filename
    output_path.write_text(result_text, encoding="utf-8")
    return output_path


def render_html_iframe(case_name: str, filename: str, html_string: str, height: int = 750):
    """
    Save HTML to a case-local file and display it with st.iframe.
    
    """
    html_path = get_case_results_dir(case_name) / filename
    html_path.write_text(html_string, encoding="utf-8")

    st.iframe(str(html_path), height=height)


def extract_json_between_markers(result_text: str, start_marker: str, end_marker: str):
    """
    Extract valid JSON between two marker strings.

    The function is tolerant of accidental markdown code fences.
    """
    pattern = rf"{re.escape(start_marker)}\s*(.*?)\s*{re.escape(end_marker)}"

    match = re.search(pattern, result_text, flags=re.DOTALL)

    if not match:
        return None

    json_text = match.group(1).strip()

    # Remove accidental markdown fences.
    json_text = re.sub(r"^```json\s*", "", json_text, flags=re.IGNORECASE)
    json_text = re.sub(r"^```\s*", "", json_text)
    json_text = re.sub(r"\s*```$", "", json_text)

    start = json_text.find("{")
    end = json_text.rfind("}")

    if start == -1 or end == -1:
        return None

    json_text = json_text[start:end + 1]

    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return None


# ============================================================
# Sidebar: Case selection
# ============================================================

st.sidebar.header("Case")

case_name = st.sidebar.text_input("New case name")

if st.sidebar.button("Create case"):
    if case_name.strip():
        create_case(case_name.strip())
        st.rerun()
    else:
        st.sidebar.warning("Please enter a case name.")

cases = list_cases()

if not cases:
    st.info("Create a case first.")
    st.stop()

selected_case = st.sidebar.selectbox("Select case", cases)


# ============================================================
# Sidebar: Skill selection
# ============================================================

st.sidebar.divider()
st.sidebar.header("Skills")

skill_id = st.sidebar.selectbox(
    "Select skill",
    list(SKILLS.keys()),
    format_func=lambda k: SKILLS[k]["name"],
)

skill = SKILLS[skill_id]


# ============================================================
# Sidebar: LLM selection
# ============================================================

st.sidebar.divider()
st.sidebar.header("LLM Provider")

if "provider" not in st.session_state:
    st.session_state["provider"] = "Anthropic / Claude"

if "model_label" not in st.session_state:
    st.session_state["model_label"] = "Claude Sonnet 4.6"

provider_options = ["OpenAI / ChatGPT", "Anthropic / Claude"]

provider = st.sidebar.selectbox(
    "Provider",
    provider_options,
    index=provider_options.index(st.session_state["provider"]),
)

st.session_state["provider"] = provider

if provider == "OpenAI / ChatGPT":
    model_labels = list(OPENAI_MODELS.keys())

    default_model = (
        st.session_state["model_label"]
        if st.session_state["model_label"] in OPENAI_MODELS
        else model_labels[0]
    )

    model_label = st.sidebar.selectbox(
        "Model",
        model_labels,
        index=model_labels.index(default_model),
    )

    selected_model = OPENAI_MODELS[model_label]

else:
    model_labels = list(ANTHROPIC_MODELS.keys())

    default_model = (
        st.session_state["model_label"]
        if st.session_state["model_label"] in ANTHROPIC_MODELS
        else model_labels[0]
    )

    model_label = st.sidebar.selectbox(
        "Model",
        model_labels,
        index=model_labels.index(default_model),
    )

    selected_model = ANTHROPIC_MODELS[model_label]

st.session_state["model_label"] = model_label

llm_config = {
    "provider": provider,
    "model_label": model_label,
    "model": selected_model,
}

st.sidebar.caption(f"Using: {model_label}")


# ============================================================
# Document preparation pipeline
# ============================================================

def auto_prepare_documents(
    case_name: str,
    docs,
    force_reprocess: bool = False,
    force_ocr: bool = False,
):
    """
    Prepare documents for all skills.

    Steps:
    1. Load document mapping if available.
    2. Reuse cached extracted text if available.
    3. Extract/OCR PDF text if needed.
    4. Reuse structured JSON if available.
    5. Structure the document using mapped role (or guess_document_type fallback).
    6. Return both raw text blocks and structured document blocks.
    """
    mapping = load_mapping(case_name)

    source_texts = []
    structured_docs = []

    progress = st.progress(0)
    status = st.empty()

    total_steps = max(len(docs) * 2, 1)
    step = 0

    for doc in docs:
        status.write(f"Extracting text from `{doc.name}`...")

        text = get_document_text(doc)

        if force_reprocess or not text:
            extract_and_cache_pdf_text(
                doc,
                force_ocr=force_ocr,
            )
            text = get_document_text(doc)

        # Determine display name and structure type from mapping or fallback
        if mapping and doc.name in mapping:
            role = mapping[doc.name]
            display_name = role
            structure_type = role_to_structure_type(role)
        else:
            display_name = doc.name
            structure_type = guess_document_type(doc.name, text or "")

        source_texts.append(
            {
                "filename": display_name,
                "text": text or "",
            }
        )

        step += 1
        progress.progress(step / total_steps)

        status.write(f"Structuring `{doc.name}`...")

        structured = None

        if not force_reprocess:
            structured = load_structured_document(case_name, doc)

        if not structured:
            structured = structure_document(
                filename=display_name,
                text=text or "",
                selected_document_type=structure_type,
            )

            save_structured_document(
                case_name,
                doc,
                structured,
            )

        structured_docs.append(structured)

        step += 1
        progress.progress(step / total_steps)

    status.write("Document preparation complete.")

    return source_texts, structured_docs


# ============================================================
# Art. 123(2) amendment visualization
# ============================================================

def get_claims_text_from_structured(structured_docs, doc_type):
    """
    Return combined claims text for a structured document type.
    """
    for doc in structured_docs:
        if doc.get("document_type") == doc_type:
            claims = doc.get("claims", [])

            if claims:
                parts = []

                for claim in claims:
                    parts.append(
                        f"Claim {claim['claim_number']}. {claim['text']}"
                    )

                return "\n\n\n".join(parts)

    return ""


def build_amendment_html(original_text, amended_text):
    """
    Build HTML diff:
    - additions in red
    - deletions in green strikethrough
    """
    original_words = original_text.split()
    amended_words = amended_text.split()

    matcher = difflib.SequenceMatcher(
        None,
        original_words,
        amended_words,
    )

    html_parts = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            html_parts.append(
                " ".join(html.escape(w) for w in original_words[i1:i2])
            )

        elif tag == "delete":
            deleted = " ".join(html.escape(w) for w in original_words[i1:i2])
            html_parts.append(
                f"<span style='color:green; text-decoration:line-through;'>{deleted}</span>"
            )

        elif tag == "insert":
            inserted = " ".join(html.escape(w) for w in amended_words[j1:j2])
            html_parts.append(
                f"<span style='color:red;'>{inserted}</span>"
            )

        elif tag == "replace":
            deleted = " ".join(html.escape(w) for w in original_words[i1:i2])
            inserted = " ".join(html.escape(w) for w in amended_words[j1:j2])

            html_parts.append(
                f"<span style='color:green; text-decoration:line-through;'>{deleted}</span> "
                f"<span style='color:red;'>{inserted}</span>"
            )

    body = " ".join(html_parts)
    body = body.replace("Claim ", "<br><br>Claim ")

    return f"""
    <div style="
        border:1px solid #ddd;
        border-radius:10px;
        padding:18px;
        background-color:#fafafa;
        font-family:Arial, sans-serif;
        font-size:15px;
        line-height:1.7;
        max-height:650px;
        overflow-y:auto;
        white-space:normal;
    ">
        <h4>Amendments in the New Set of Claims</h4>
        <p>
            <span style="color:red;">Red</span> = additions<br>
            <span style="color:green; text-decoration:line-through;">Green strikethrough</span> = deletions
        </p>
        <hr>
        {body}
    </div>
    """


# ============================================================
# Technical Features UI
# ============================================================

def extract_technical_features_json(result_text):
    """
    Extract JSON from the Technical Features skill result.
    """
    return extract_json_between_markers(
        result_text,
        "BEGIN_TECHNICAL_FEATURES_JSON",
        "END_TECHNICAL_FEATURES_JSON",
    )


def build_feature_data_from_structured_docs(structured_docs):
    """
    Fallback data if Technical Features JSON cannot be parsed.

    This fallback uses the already parsed claims.
    It does not perform fine-grained feature splitting.
    """
    claim_overview = []
    features = []

    for doc in structured_docs:
        for claim in doc.get("claims", []):
            claim_no = claim.get("claim_number")
            claim_text = claim.get("text", "")

            dependency = (
                "independent"
                if claim.get("is_independent_guess")
                else "dependent"
            )

            claim_overview.append(
                {
                    "claim_number": claim_no,
                    "dependency": dependency,
                    "claim_type": "unclear",
                    "main_subject": claim_text[:120],
                }
            )

            features.append(
                {
                    "claim_number": claim_no,
                    "feature_text": claim_text,
                }
            )

    return {
        "claim_overview": claim_overview,
        "features": features,
        "method_steps": [],
        "dependent_claims": [],
        "essential_features": [],
        "examiner_summary": "",
    }


def build_claim_feature_matrix(data):
    """
    Build editable Technical Features matrix:
    - one claim per column
    - consecutive feature rows
    - independent claims marked by 🔴 in the column header
    - feature IDs are not displayed inside cells
    """
    claim_overview = data.get("claim_overview", [])
    features = data.get("features", [])

    claim_numbers = set()

    for item in claim_overview:
        if item.get("claim_number") is not None:
            claim_numbers.add(normalize_claim_number(item.get("claim_number")))

    for item in features:
        if item.get("claim_number") is not None:
            claim_numbers.add(normalize_claim_number(item.get("claim_number")))

    claim_numbers = sorted(claim_numbers)

    independent_claims = set()

    for item in claim_overview:
        claim_no = normalize_claim_number(item.get("claim_number"))
        dependency = str(item.get("dependency", "")).lower()

        if "independent" in dependency:
            independent_claims.add(claim_no)

    claim_features = {claim_no: [] for claim_no in claim_numbers}

    for feature in features:
        claim_no = normalize_claim_number(feature.get("claim_number"))
        feature_text = str(feature.get("feature_text", "")).strip()

        if feature_text and claim_no in claim_features:
            claim_features[claim_no].append(feature_text)

    max_rows = max([len(v) for v in claim_features.values()] + [1])

    table_data = {}

    for claim_no in claim_numbers:
        col_name = (
            f"🔴 Claim {claim_no}"
            if claim_no in independent_claims
            else f"Claim {claim_no}"
        )

        values = claim_features.get(claim_no, [])
        values = values + [""] * (max_rows - len(values))
        table_data[col_name] = values

    return pd.DataFrame(table_data)


def render_technical_features_ui(data):
    """
    Render Technical Features output as one editable matrix.
    """
    st.header("Technical Features Matrix")

    matrix_df = build_claim_feature_matrix(data)

    if matrix_df.empty:
        st.warning("No technical feature matrix could be generated.")
        return

    st.data_editor(
        matrix_df,
        num_rows="dynamic",
        width="stretch",
        key="technical_feature_matrix_editor",
    )

    st.caption(
        "Each column is one claim. 🔴 marks an independent claim. "
        "You can edit cells, delete content, or add new feature rows."
    )


# ============================================================
# Novelty / Inventive Step UI
# ============================================================

def extract_novelty_is_json(result_text):
    """
    Extract JSON from the Novelty/Inventive Step skill result.
    """
    return extract_json_between_markers(
        result_text,
        "BEGIN_NOVELTY_IS_JSON",
        "END_NOVELTY_IS_JSON",
    )


def build_novelty_matrix(data):
    """
    Build editable novelty matrix:

    Claim | Feature | D1 | D2 | D3 | ...

    Prior-art cells contain coverage status, reference sign, basis, and disclosure.
    """
    mapping_table = data.get("mapping_table", [])

    document_labels = []

    for doc in data.get("prior_art_documents", []):
        label = doc.get("label")
        if label and label not in document_labels:
            document_labels.append(label)

    for row in mapping_table:
        documents = row.get("documents", {})
        for label in documents.keys():
            if label not in document_labels:
                document_labels.append(label)

    rows = []

    for row in mapping_table:
        table_row = {
            "Claim": row.get("claim"),
            "Feature": row.get("feature"),
        }

        documents = row.get("documents", {})

        for label in document_labels:
            doc_cell = documents.get(label, {})

            status = doc_cell.get("status", "UNCLEAR")
            ref = doc_cell.get("reference_sign", "")
            basis = doc_cell.get("basis", "")
            disclosure = doc_cell.get("disclosure", "")
            comment = doc_cell.get("comment", "")

            if status == "NOT COVERED":
                cell_text = "NOT COVERED"
            else:
                cell_text = (
                    f"{status}\n"
                    f"Ref.: {ref}\n"
                    f"Basis: {basis}\n"
                    f"Disclosure: {disclosure}\n"
                    f"Comment: {comment}"
                ).strip()

            table_row[label] = cell_text

        rows.append(table_row)

    return pd.DataFrame(rows), document_labels


def render_novelty_matrix_html(df):
    """
    Styled preview for the novelty matrix.

    NOT COVERED cells are highlighted red.
    """
    html_parts = []

    html_parts.append(
        """
        <div style="overflow-x:auto;">
        <table style="
            border-collapse:collapse;
            width:100%;
            font-family:Arial, sans-serif;
            font-size:14px;
        ">
        <thead><tr>
        """
    )

    for col in df.columns:
        html_parts.append(
            f"<th style='border:1px solid #ccc; padding:8px; background:#f2f2f2; text-align:left;'>{html.escape(str(col))}</th>"
        )

    html_parts.append("</tr></thead><tbody>")

    for _, row in df.iterrows():
        html_parts.append("<tr>")

        for col in df.columns:
            value = str(row[col]) if pd.notna(row[col]) else ""

            if col not in ["Claim", "Feature"] and value.strip().startswith("NOT COVERED"):
                style = (
                    "border:1px solid #ddd;"
                    "padding:8px;"
                    "vertical-align:top;"
                    "background-color:#ffcccc;"
                    "white-space:pre-wrap;"
                    "min-width:220px;"
                )
            else:
                style = (
                    "border:1px solid #ddd;"
                    "padding:8px;"
                    "vertical-align:top;"
                    "white-space:pre-wrap;"
                    "min-width:220px;"
                )

            html_parts.append(
                f"<td style='{style}'>{html.escape(value)}</td>"
            )

        html_parts.append("</tr>")

    html_parts.append("</tbody></table></div>")

    return "\n".join(html_parts)


def render_novelty_is_ui(data):
    """
    Render only the final editable Novelty / Inventive Step mapping table.

    Final table structure:
        Claim | Feature | D1 | D2 | D3 | ...

    NOT COVERED cells are shown in red in the styled preview.
    """
    st.header("Novelty / Inventive Step Feature Mapping")

    df, _ = build_novelty_matrix(data)

    if df.empty:
        st.warning("No novelty mapping table could be generated.")
        return

    st.subheader("Editable final table")

    column_config = {
        col: st.column_config.TextColumn(
            col,
            width="large",
        )
        for col in df.columns
    }

    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        width="stretch",
        column_config=column_config,
        key="novelty_is_matrix_editor",
    )

    st.caption(
        "Edit the table above. Cells containing NOT COVERED are highlighted red "
        "in the preview below."
    )

    st.subheader("Final table preview")

    styled_html = render_novelty_matrix_html(edited_df)

    render_html_iframe(
        selected_case,
        f"{selected_case}_novelty_preview.html",
        styled_html,
        height=750,
    )

    if st.button("Save edited final table"):
        output_path = (
            get_case_results_dir(selected_case)
            / f"{selected_case}_final_novelty_table.csv"
        )

        edited_df.to_csv(
            output_path,
            index=False,
            encoding="utf-8-sig",
        )

        st.success(f"Final novelty table saved to: `{output_path}`")

# ============================================================
# Tabs
# ============================================================

tabs = st.tabs(
    [
        "1. Documents",
        "2. Run Analysis",
        "3. Results",
    ]
)


# ============================================================
# Tab 1: Documents
# ============================================================

with tabs[0]:
    st.header("Upload Documents")

    st.info(f"Current case: **{selected_case}**")

    uploaded_files = st.file_uploader(
        "Upload PDF documents",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        if st.button("Save uploaded PDFs"):
            for uploaded_file in uploaded_files:
                save_uploaded_pdf(selected_case, uploaded_file)

            st.success("PDF files saved.")
            st.rerun()

    with st.expander("Advanced: storage information"):
        st.write("Selected case:", selected_case)
        st.write("PDF folder:", str(pdf_dir(selected_case).resolve()))
        st.write("Folder exists:", pdf_dir(selected_case).exists())

        docs = list_case_documents(selected_case)

        if docs:
            st.write("Stored PDFs:")
            for doc in docs:
                st.write(f"- `{doc.name}`")
        else:
            st.write("No PDFs stored yet.")


# ============================================================
# Tab 2: Run Analysis
# ============================================================

with tabs[1]:
    st.header("Run Full Analysis")

    st.info(
        f"Skill: **{skill['name']}**  \n"
        f"Model: **{provider} / {model_label}**"
    )

    docs = list_case_documents(selected_case)

    if not docs:
        st.warning("Upload PDFs first.")
    else:
        selected_docs = st.multiselect(
            "Select documents to use",
            docs,
            format_func=lambda p: p.name,
            default=docs,
        )

        with st.expander("Advanced options"):
            force_reprocess = st.checkbox(
                "Re-extract and re-structure documents",
                value=False,
            )

            force_ocr = st.checkbox(
                "Force OCR",
                value=False,
                help="Use only if PDFs are scanned or text extraction is poor.",
            )

        if st.button("Run Full Analysis", type="primary"):
            if not selected_docs:
                st.warning("Please select at least one document.")
            else:
                with st.spinner("Preparing documents and running analysis..."):
                    source_texts, structured_docs = auto_prepare_documents(
                        case_name=selected_case,
                        docs=selected_docs,
                        force_reprocess=force_reprocess,
                        force_ocr=force_ocr,
                    )

                    result = skill["run"](
                        case_name=selected_case,
                        source_documents=source_texts,
                        structured_documents=structured_docs,
                        user_input={},
                        llm_config=llm_config,
                    )

                st.session_state["last_result"] = result
                st.session_state["last_skill_id"] = skill_id
                st.session_state["last_structured_docs"] = structured_docs

                # Save full hidden text outputs for UI-based skills.
                if skill_id == "technical_features":
                    features_file = save_text_result(
                        selected_case,
                        f"{selected_case}_features.txt",
                        result,
                    )
                    st.session_state["features_file"] = str(features_file)
                    st.session_state["novelty_file"] = None

                elif skill_id == "novelty_inventive_step":
                    novelty_file = save_text_result(
                        selected_case,
                        f"{selected_case}_novelty_inventive_step.txt",
                        result,
                    )
                    st.session_state["novelty_file"] = str(novelty_file)
                    st.session_state["features_file"] = None

                else:
                    st.session_state["features_file"] = None
                    st.session_state["novelty_file"] = None

                # Art. 123(2) amendment comparison is only relevant for that skill.
                claims_as_filed_text = get_claims_text_from_structured(
                    structured_docs,
                    "claims_as_filed",
                )

                amended_claims_text = get_claims_text_from_structured(
                    structured_docs,
                    "amended_claims",
                )

                if (
                    skill_id == "epo_123_2"
                    and claims_as_filed_text
                    and amended_claims_text
                ):
                    amendment_html = build_amendment_html(
                        claims_as_filed_text,
                        amended_claims_text,
                    )
                    st.session_state["amendment_html"] = amendment_html
                else:
                    st.session_state["amendment_html"] = None

                st.success("Analysis completed.")

                if st.session_state.get("amendment_html"):
                    render_html_iframe(
                        selected_case,
                        f"{selected_case}_amendment_preview.html",
                        st.session_state["amendment_html"],
                        height=700,
                    )


# ============================================================
# Tab 3: Results
# ============================================================

with tabs[2]:
    st.header("Result")

    result = st.session_state.get("last_result")
    result_skill_id = st.session_state.get("last_skill_id", skill_id)

    if not result:
        st.info("No result yet.")
        st.stop()

    if result_skill_id == "technical_features":
        data = extract_technical_features_json(result)

        if data is None:
            structured_docs = st.session_state.get("last_structured_docs", [])
            data = build_feature_data_from_structured_docs(structured_docs)

        render_technical_features_ui(data)

        features_file = st.session_state.get("features_file")

        if features_file:
            st.success(
                f"Full technical-features analysis saved to: `{features_file}`"
            )

    elif result_skill_id == "novelty_inventive_step":
        data = extract_novelty_is_json(result)

        if data:
            render_novelty_is_ui(data)

            novelty_file = st.session_state.get("novelty_file")

            if novelty_file:
                st.success(
                    f"Full novelty/inventive-step analysis saved to: `{novelty_file}`"
                )

        else:
            st.warning(
                "Novelty/Inventive Step JSON could not be parsed. "
                "The Markdown result is shown below."
            )

            st.markdown(result)

            st.download_button(
                "Download result as Markdown",
                data=result,
                file_name=f"{selected_case}_{result_skill_id}_result.md",
                mime="text/markdown",
            )

    elif result_skill_id == "basic_analysis":
        analysis_data = result if isinstance(result, dict) else {"result": result, "summary": ""}

        st.markdown(analysis_data["result"])

        st.download_button(
            "Download full analysis as Markdown",
            data=analysis_data["result"],
            file_name=f"{selected_case}_basic_analysis_result.md",
            mime="text/markdown",
        )

        summary = analysis_data.get("summary", "")
        if summary:
            st.divider()
            st.subheader("Summary")
            st.markdown(summary)
            st.download_button(
                "Download Summary (.txt)",
                data=summary,
                file_name=f"Summary_{selected_case}.txt",
                mime="text/plain",
            )

    else:
        st.markdown(result)

        st.download_button(
            "Download result as Markdown",
            data=result,
            file_name=f"{selected_case}_{result_skill_id}_result.md",
            mime="text/markdown",
        )