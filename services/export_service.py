import io
import json
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Adds page numbers and running footer to all pages."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Running top subtle rule
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, letter[1] - 40, letter[0] - 54, letter[1] - 40)
        self.drawString(54, letter[1] - 35, "Smart Study  •  AI Study Companion")

        # Running footer
        self.line(54, 45, letter[0] - 54, 45)
        self.drawString(54, 32, "Generated with Smart Study AI")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 54, 32, page_str)
        self.restoreState()


def get_custom_styles():
    styles = getSampleStyleSheet()
    
    # Custom styles
    styles.add(ParagraphStyle(
        name="DocTitle",
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=6
    ))
    
    styles.add(ParagraphStyle(
        name="DocSubtitle",
        fontName="Helvetica",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#4F46E5"),
        spaceAfter=15
    ))
    
    styles.add(ParagraphStyle(
        name="SectionHeading",
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        name="SubsectionHeading",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#334155"),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        name="BodyTextCustom",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6
    ))

    styles.add(ParagraphStyle(
        name="BulletCustom",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#334155"),
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    ))

    styles.add(ParagraphStyle(
        name="CalloutText",
        fontName="Helvetica-Oblique",
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#475569")
    ))

    styles.add(ParagraphStyle(
        name="MetaText",
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#64748B")
    ))

    return styles


def build_header(elements, styles, title, filename):
    elements.append(Paragraph(f"Smart Study: {title}", styles["DocTitle"]))
    meta_str = f"Document: <b>{filename}</b> &nbsp;|&nbsp; Date: {datetime.now().strftime('%B %d, %Y')}"
    elements.append(Paragraph(meta_str, styles["MetaText"]))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=14))


def format_summary_content(elements, styles, summary_data):
    if not summary_data:
        elements.append(Paragraph("No summary content available.", styles["BodyTextCustom"]))
        return

    # 1. Overview
    if summary_data.get("overview"):
        elements.append(Paragraph("1. Overview", styles["SectionHeading"]))
        elements.append(Paragraph(summary_data["overview"], styles["BodyTextCustom"]))
        elements.append(Spacer(1, 8))

    # 2. Key Concepts
    key_concepts = summary_data.get("key_concepts", [])
    if key_concepts:
        elements.append(Paragraph("2. Key Concepts", styles["SectionHeading"]))
        for kc in key_concepts:
            if isinstance(kc, dict):
                title = kc.get("title", "")
                desc = kc.get("description", "")
                elements.append(Paragraph(f"• <b>{title}</b>: {desc}", styles["BulletCustom"]))
            else:
                elements.append(Paragraph(f"• {str(kc)}", styles["BulletCustom"]))
        elements.append(Spacer(1, 8))

    # 3. Important Points
    imp_points = summary_data.get("important_points", [])
    if imp_points:
        elements.append(Paragraph("3. Important Points", styles["SectionHeading"]))
        for pt in imp_points:
            elements.append(Paragraph(f"• {str(pt)}", styles["BulletCustom"]))
        elements.append(Spacer(1, 8))

    # 4. Exam-Focused Points
    exam_pts = summary_data.get("exam_focused_points", [])
    if exam_pts:
        elements.append(Paragraph("4. Exam-Focused Points", styles["SectionHeading"]))
        for ep in exam_pts:
            elements.append(Paragraph(f"★ <b>High-Yield:</b> {str(ep)}", styles["BulletCustom"]))
        elements.append(Spacer(1, 8))

    # 5. Short Revision Notes
    rev_notes = summary_data.get("revision_notes", [])
    if rev_notes:
        elements.append(Paragraph("5. Short Revision Notes", styles["SectionHeading"]))
        for rn in rev_notes:
            elements.append(Paragraph(f"✔ {str(rn)}", styles["BulletCustom"]))
        elements.append(Spacer(1, 8))


def format_questions_content(elements, styles, questions_data):
    if not questions_data:
        elements.append(Paragraph("No important questions generated yet.", styles["BodyTextCustom"]))
        return

    elements.append(Paragraph("Important Exam Questions & Model Answers", styles["SectionHeading"]))
    elements.append(Spacer(1, 6))

    for idx, q in enumerate(questions_data, 1):
        q_text = q.get("question", "")
        a_text = q.get("answer", "")
        exp = q.get("explanation", "")

        q_block = [
            Paragraph(f"<b>Q{idx}. {q_text}</b>", styles["SubsectionHeading"]),
            Paragraph(f"<b>Answer:</b> {a_text}", styles["BodyTextCustom"])
        ]
        if exp:
            q_block.append(Paragraph(f"<i>Tip / Explanation:</i> {exp}", styles["CalloutText"]))
        q_block.append(Spacer(1, 8))
        elements.append(KeepTogether(q_block))


def format_flashcards_content(elements, styles, flashcards_data):
    if not flashcards_data:
        elements.append(Paragraph("No flashcards generated yet.", styles["BodyTextCustom"]))
        return

    elements.append(Paragraph("Smart Study Flashcards", styles["SectionHeading"]))
    elements.append(Paragraph("Use these cards for quick active recall and memorization.", styles["BodyTextCustom"]))
    elements.append(Spacer(1, 8))

    for idx, card in enumerate(flashcards_data, 1):
        front = card.get("front", "")
        back = card.get("back", "")
        hint = card.get("hint", "")

        hint_line = f"<br/><font color='#64748B' size='8'><i>Hint: {hint}</i></font>" if hint else ""
        card_table_data = [
            [Paragraph(f"<b>Card {idx} [FRONT / CONCEPT]</b>", styles["SubsectionHeading"])],
            [Paragraph(front + hint_line, styles["BodyTextCustom"])],
            [Paragraph("<b>[BACK / EXPLANATION]</b>", styles["SubsectionHeading"])],
            [Paragraph(back, styles["BodyTextCustom"])]
        ]

        t = Table(card_table_data, colWidths=[500])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
            ("LINEBELOW", (0, 1), (0, 1), 1, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(KeepTogether([t, Spacer(1, 10)]))


def format_mcqs_content(elements, styles, mcqs_data):
    if not mcqs_data:
        elements.append(Paragraph("No MCQs generated yet.", styles["BodyTextCustom"]))
        return

    elements.append(Paragraph("Practice Multiple Choice Questions (MCQ)", styles["SectionHeading"]))
    elements.append(Spacer(1, 6))

    for idx, mcq in enumerate(mcqs_data, 1):
        q_text = mcq.get("question", "")
        options = mcq.get("options", [])
        correct = mcq.get("correct_answer", "")
        exp = mcq.get("explanation", "")

        mcq_block = [
            Paragraph(f"<b>{idx}. {q_text}</b>", styles["SubsectionHeading"])
        ]
        for opt in options:
            mcq_block.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;{opt}", styles["BodyTextCustom"]))
        
        mcq_block.append(Paragraph(f"<b>Correct Answer:</b> Option {correct}", styles["BodyTextCustom"]))
        if exp:
            mcq_block.append(Paragraph(f"<b>Explanation:</b> {exp}", styles["CalloutText"]))
        mcq_block.append(Spacer(1, 10))
        elements.append(KeepTogether(mcq_block))


def generate_pdf_export(content_type, filename, raw_data):
    """
    Creates and returns a PDF BytesIO stream.
    content_type: 'summary', 'questions', 'flashcards', 'mcqs', or 'combined'
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = get_custom_styles()
    elements = []

    titles_map = {
        "summary": "Study Summary & Revision Notes",
        "questions": "Important Questions & Answers",
        "flashcards": "Flashcards Collection",
        "mcqs": "Practice MCQ Quiz & Solutions",
        "combined": "Comprehensive Study Guide"
    }

    doc_title = titles_map.get(content_type, "Study Notes")
    build_header(elements, styles, doc_title, filename)

    # Parse JSON data if string passed
    data = raw_data
    if isinstance(raw_data, str):
        try:
            data = json.loads(raw_data)
        except Exception:
            data = raw_data

    if content_type == "summary":
        format_summary_content(elements, styles, data)
    elif content_type == "questions":
        format_questions_content(elements, styles, data)
    elif content_type == "flashcards":
        format_flashcards_content(elements, styles, data)
    elif content_type == "mcqs":
        format_mcqs_content(elements, styles, data)
    elif content_type == "combined":
        # Data is dict containing all contents: {'summary': ..., 'questions': ..., etc.}
        if "summary" in data:
            s_data = json.loads(data["summary"]) if isinstance(data["summary"], str) else data["summary"]
            format_summary_content(elements, styles, s_data)
            elements.append(Spacer(1, 14))

        if "questions" in data:
            q_data = json.loads(data["questions"]) if isinstance(data["questions"], str) else data["questions"]
            format_questions_content(elements, styles, q_data)
            elements.append(Spacer(1, 14))

        if "flashcards" in data:
            f_data = json.loads(data["flashcards"]) if isinstance(data["flashcards"], str) else data["flashcards"]
            format_flashcards_content(elements, styles, f_data)
            elements.append(Spacer(1, 14))

        if "mcqs" in data:
            m_data = json.loads(data["mcqs"]) if isinstance(data["mcqs"], str) else data["mcqs"]
            format_mcqs_content(elements, styles, m_data)

    doc.build(elements, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer
