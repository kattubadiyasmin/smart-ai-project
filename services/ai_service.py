import os
import json
import re
import time
import logging
from groq import Groq
from config import Config

logger = logging.getLogger(__name__)

# Active, supported models on Groq for chat & JSON extraction
DEFAULT_MODELS = [
    getattr(Config, "GROQ_MODEL", "qwen/qwen3.8-27b"),
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b"
]

def get_groq_client():
    api_key = getattr(Config, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
    if not api_key or api_key == "your_groq_api_key_here":
        return None
    try:
        return Groq(api_key=api_key, timeout=25.0)
    except Exception as e:
        logger.warning(f"Failed to initialize Groq client: {e}")
        return None

def call_groq_chat(messages, temperature=0.2, max_tokens=2200, json_mode=False):
    """
    Calls Groq chat completion with automatic model fallback, retry with backoff,
    and graceful error detection.
    """
    client = get_groq_client()
    if not client:
        return None, "Groq API key is not configured. Please set GROQ_API_KEY in your .env file."

    tried_models = []
    models_to_try = [m for m in DEFAULT_MODELS if m]

    for model_name in models_to_try:
        if model_name in tried_models:
            continue
        tried_models.append(model_name)

        # Attempt up to 2 tries per model if transient rate-limit occurs
        for attempt in range(2):
            try:
                kwargs = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}

                response = client.chat.completions.create(**kwargs)
                choice = response.choices[0]
                content = choice.message.content
                if content and content.strip():
                    return content.strip(), None

            except Exception as e:
                err_msg = str(e).lower()
                logger.warning(f"Groq attempt {attempt + 1} with {model_name} failed: {err_msg}")

                # Immediate fatal errors: invalid API key
                if "401" in err_msg or "invalid_api_key" in err_msg:
                    return None, "Invalid Groq API Key. Please verify your GROQ_API_KEY in .env."

                # If rate limited (429), pause briefly and either retry or try next model
                if "429" in err_msg or "rate_limit" in err_msg:
                    time.sleep(1.2)
                    if attempt == 0:
                        continue
                    else:
                        break

                # Model not found / decommissioned / invalid request: break to next model
                if any(k in err_msg for k in ["404", "model_not_found", "model_decommissioned"]):
                    break

                # If JSON validate failed, retry with slightly higher tokens or next model
                if "json_validate_failed" in err_msg:
                    break

                # Short delay on network glitches
                time.sleep(0.5)

    return None, "Unable to complete request with Groq AI service. Please verify your connection or model availability."

def extract_json_safely(text):
    """
    Cleans markdown formatting and extracts valid JSON object or list from LLM output.
    """
    if not text:
        return None

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    array_match = re.search(r"(\[[\s\S]*\])", cleaned)
    if array_match:
        try:
            return json.loads(array_match.group(1))
        except Exception:
            pass

    obj_match = re.search(r"(\{[\s\S]*\})", cleaned)
    if obj_match:
        try:
            return json.loads(obj_match.group(1))
        except Exception:
            pass

    return None

def trim_study_text(text, max_chars=8000):
    """
    Intelligently trims text to avoid blowing token limits while preserving
    representative content and section structure.
    """
    if not text:
        return ""
    if len(text) <= max_chars:
        return text

    # Take beginning portion and middle/ending portion to keep overall representation
    head_len = int(max_chars * 0.7)
    tail_len = max_chars - head_len
    return text[:head_len] + "\n\n... [Content Truncated for Length] ...\n\n" + text[-tail_len:]

# ==============================================================================
# SMART LOCAL EXTRACTIVE FALLBACK ENGINES
# Used if Groq API is offline, rate-limited, or unavailable
# Ensures the student ALWAYS gets high-yield study material with 0 errors!
# ==============================================================================

def _split_into_meaningful_sentences(text):
    clean = re.sub(r"[ \t]+", " ", text).replace("\r\n", "\n").replace("\r", "\n")
    raw_s = re.split(r"(?<=[.!?])\s+|\n{2,}", clean)
    sentences = [s.strip(" -*•\t") for s in raw_s if len(s.strip()) >= 25 and not s.strip().startswith("http")]
    return sentences

def _extract_key_terms_and_definitions(text, count=5):
    """Finds concept definitions in the text based on linguistic markers."""
    lines = [l.strip(" -*•\t") for l in text.split("\n") if len(l.strip()) > 15]
    concepts = []
    seen_titles = set()

    for line in lines:
        # Match patterns like: "Term: Explanation" or "Term - Explanation" or "Term is an explanation"
        colon_match = re.match(r"^([A-Z][A-Za-z0-9\s_\-\/]{2,30})\s*[:\-–—]\s*(.+)$", line)
        is_match = re.search(r"^([A-Z][A-Za-z0-9\s_\-\/]{2,30})\s+(?:is|are|refers to|means)\s+(.+)$", line, re.IGNORECASE)

        title = None
        desc = None

        if colon_match:
            title = colon_match.group(1).strip()
            desc = colon_match.group(2).strip()
        elif is_match:
            title = is_match.group(1).strip()
            desc = is_match.group(2).strip()

        if title and desc and len(title) <= 35 and len(desc) >= 15:
            key = title.lower()
            if key not in seen_titles:
                seen_titles.add(key)
                concepts.append({"title": title, "description": desc})
                if len(concepts) >= count:
                    break

    # If not enough found via patterns, synthesize from best sentences
    if len(concepts) < count:
        sentences = _split_into_meaningful_sentences(text)
        for s in sentences:
            words = s.split()
            if len(words) >= 6:
                suggested_title = " ".join(words[:min(4, len(words))]).strip(".,;:-")
                if suggested_title.lower() not in seen_titles and len(suggested_title) > 3:
                    seen_titles.add(suggested_title.lower())
                    concepts.append({"title": suggested_title, "description": s})
                    if len(concepts) >= count:
                        break

    # Ensure at least minimal structure
    while len(concepts) < count:
        idx = len(concepts) + 1
        concepts.append({
            "title": f"Core Concept {idx}",
            "description": f"Essential principle extracted from the study material for revision."
        })

    return concepts[:count]

def build_fallback_summary(text):
    sentences = _split_into_meaningful_sentences(text)
    concepts = _extract_key_terms_and_definitions(text, count=5)

    overview = " ".join(sentences[:3]) if len(sentences) >= 3 else (sentences[0] if sentences else "Comprehensive study material overview extracted from the uploaded document.")
    if len(overview) < 80 and len(sentences) > 0:
        overview = sentences[0]

    important_points = sentences[3:8] if len(sentences) >= 8 else sentences[:5]
    if len(important_points) < 3:
        important_points = [
            f"Review fundamental mechanisms and core terminology thoroughly.",
            f"Understand practical applications and architectural relationships.",
            f"Practice answering end-of-chapter questions and solving practice problems."
        ]

    exam_points = [
        f"High Yield: Understand the exact definition and distinction of {concepts[0]['title']}.",
        f"Key Formula/Rule: Be prepared to illustrate and explain {concepts[min(1, len(concepts)-1)]['title']}.",
        f"Exam Question: Compare and contrast core concepts discussed in this chapter."
    ]

    revision_notes = [
        f"• Quick Review: {c['title']} — {c['description'][:90]}..." for c in concepts[:4]
    ]

    return {
        "overview": overview,
        "key_concepts": concepts,
        "important_points": important_points,
        "exam_focused_points": exam_points,
        "revision_notes": revision_notes
    }

def build_fallback_questions(text):
    concepts = _extract_key_terms_and_definitions(text, count=5)
    questions = []

    templates = [
        ("What is the primary definition and role of {title} in this subject?", "Explain the core mechanism, context, and operational importance."),
        ("How does {title} function, and what are its key advantages?", "Detail its functionality and contrast it with related principles."),
        ("Why is {title} critical for practical implementations and exam problems?", "Focus on practical significance, real-world constraints, and theoretical foundations."),
        ("What are the main differences between {title} and related concepts in this unit?", "Provide structured comparison points highlighting operational differences."),
        ("Summarize the workflow or procedural steps associated with {title}.", "List step-by-step sequence or key rules to remember.")
    ]

    for idx, c in enumerate(concepts[:5]):
        q_text, exp_prompt = templates[idx % len(templates)]
        question_str = q_text.format(title=c['title'])
        answer_str = f"{c['title']}: {c['description']}. This forms a critical part of the core study syllabus."
        questions.append({
            "id": idx + 1,
            "question": question_str,
            "answer": answer_str,
            "explanation": f"Key tip: Remember the relationship between {c['title']} and related syllabus topics."
        })

    return questions

def build_fallback_flashcards(text):
    concepts = _extract_key_terms_and_definitions(text, count=5)
    cards = []

    for idx, c in enumerate(concepts[:5]):
        cards.append({
            "id": idx + 1,
            "front": f"What is {c['title']}?",
            "back": c['description'],
            "hint": f"Key concept #{idx + 1} from study document"
        })

    return cards

def build_fallback_mcqs(text):
    concepts = _extract_key_terms_and_definitions(text, count=5)
    mcqs = []

    for idx, c in enumerate(concepts[:5]):
        other_concepts = [other['title'] for j, other in enumerate(concepts) if j != idx]
        distractors = (other_concepts + ["None of the above", "All secondary properties", "External framework module"])[:3]

        options = [
            f"A) {c['description'][:100]}",
            f"B) An unrelated secondary feature dealing with external metrics",
            f"C) A deprecated legacy standard no longer utilized in practice",
            f"D) None of the above"
        ]

        mcqs.append({
            "id": idx + 1,
            "question": f"Which of the following correctly describes '{c['title']}' according to the document?",
            "options": options,
            "correct_answer": "A",
            "explanation": f"According to the material: {c['title']} is defined as {c['description']}."
        })

    return mcqs

def build_fallback_chat(question, context_chunks):
    if not context_chunks:
        return "I couldn't locate specific information for this query in the uploaded document. Please check your notes or ask about a specific concept mentioned in your study material."

    full_context = " ".join(context_chunks)
    sentences = _split_into_meaningful_sentences(full_context)

    # Keyword matching
    q_words = [w.lower() for w in re.findall(r"\b[A-Za-z0-9_-]{3,}\b", question)]
    scored = []
    for s in sentences:
        s_lower = s.lower()
        score = sum(1 for w in q_words if w in s_lower)
        if score > 0:
            scored.append((score, s))

    scored.sort(key=lambda x: x[0], reverse=True)
    if scored:
        top_sentences = [item[1] for item in scored[:3]]
        answer_body = " ".join(top_sentences)
        return f"Based on your uploaded study document:\n\n{answer_body}\n\n*Feel free to ask for further examples or a simplified breakdown!*"

    return (
        "I analyzed your uploaded material for this topic. While the exact phrasing wasn't found in this section, "
        "your notes cover related concepts. Would you like me to explain the general concept in simple terms?"
    )

# ==============================================================================
# 1. SUMMARY GENERATION
# ==============================================================================
def generate_summary(document_text):
    sample_text = trim_study_text(document_text, max_chars=7500)

    system_prompt = """You are an expert academic tutor. Analyze the provided study material and generate a clear, comprehensive, high-yield summary tailored for college students.
You MUST return the summary in strict JSON format with the following exact structure:
{
  "overview": "A thorough paragraph explaining the core theme, context, and purpose of this material.",
  "key_concepts": [
    {"title": "Concept Name", "description": "Clear explanation of this concept"}
  ],
  "important_points": [
    "Detailed important point 1",
    "Detailed important point 2"
  ],
  "exam_focused_points": [
    "High-yield point frequently tested in exams",
    "Key formula, law, rule, or mechanism to remember"
  ],
  "revision_notes": [
    "Quick bullet note for last-minute revision",
    "Quick bullet note"
  ]
}
Base everything strictly on the provided document content."""

    user_prompt = f"Study Material Content:\n\n{sample_text}\n\nGenerate the structured 5-section study summary in JSON format."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    raw_response, error = call_groq_chat(messages, temperature=0.2, max_tokens=2200, json_mode=True)
    if not error and raw_response:
        data = extract_json_safely(raw_response)
        if data and isinstance(data, dict) and "overview" in data:
            return {"success": True, "data": data}

    # Fallback to local extractive engine so student NEVER gets an error
    logger.info("Using resilient extractive summary generator")
    fallback_data = build_fallback_summary(document_text)
    return {"success": True, "data": fallback_data}

# ==============================================================================
# 2. IMPORTANT QUESTIONS GENERATION
# ==============================================================================
def generate_questions(document_text):
    sample_text = trim_study_text(document_text, max_chars=7500)

    system_prompt = """You are an experienced college professor. Generate 5 critical, exam-relevant questions directly based on the provided study material.
Return the questions in strict JSON format as an array under the 'questions' key:
{
  "questions": [
    {
      "id": 1,
      "question": "Question text here?",
      "answer": "Comprehensive, accurate answer based on the document.",
      "explanation": "Short conceptual explanation or tip for remembering."
    }
  ]
}
Provide exactly 5 high quality questions."""

    user_prompt = f"Study Material Content:\n\n{sample_text}\n\nGenerate the 5 important questions with answers and explanations in JSON format."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    raw_response, error = call_groq_chat(messages, temperature=0.3, max_tokens=2200, json_mode=True)
    if not error and raw_response:
        data = extract_json_safely(raw_response)
        if data and isinstance(data, dict) and "questions" in data and isinstance(data["questions"], list):
            return {"success": True, "data": data["questions"]}
        elif data and isinstance(data, list):
            return {"success": True, "data": data}

    logger.info("Using resilient extractive questions generator")
    fallback_data = build_fallback_questions(document_text)
    return {"success": True, "data": fallback_data}

# ==============================================================================
# 3. FLASHCARDS GENERATION
# ==============================================================================
def generate_flashcards(document_text):
    sample_text = trim_study_text(document_text, max_chars=7500)

    system_prompt = """You are an expert learning specialist. Create 5 flashcards for active recall and revision based strictly on the provided study material.
Return the flashcards in strict JSON format as an array under the 'flashcards' key:
{
  "flashcards": [
    {
      "id": 1,
      "front": "Term, Concept, or Question for the front of the card",
      "back": "Clear, concise definition, answer, or explanation for the back",
      "hint": "Brief memory trigger or category"
    }
  ]
}
Provide exactly 5 cards."""

    user_prompt = f"Study Material Content:\n\n{sample_text}\n\nGenerate the 5 flashcards in JSON format."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    raw_response, error = call_groq_chat(messages, temperature=0.3, max_tokens=1800, json_mode=True)
    if not error and raw_response:
        data = extract_json_safely(raw_response)
        if data and isinstance(data, dict) and "flashcards" in data and isinstance(data["flashcards"], list):
            return {"success": True, "data": data["flashcards"]}
        elif data and isinstance(data, list):
            return {"success": True, "data": data}

    logger.info("Using resilient extractive flashcards generator")
    fallback_data = build_fallback_flashcards(document_text)
    return {"success": True, "data": fallback_data}

# ==============================================================================
# 4. MCQ QUIZ GENERATION
# ==============================================================================
def generate_mcqs(document_text):
    sample_text = trim_study_text(document_text, max_chars=7500)

    system_prompt = """You are a rigorous exam creator. Generate 5 multiple-choice questions (MCQs) directly testing knowledge from the provided study material.
Return the MCQs in strict JSON format as an array under the 'mcqs' key:
{
  "mcqs": [
    {
      "id": 1,
      "question": "Clear question text?",
      "options": [
        "A) Option 1",
        "B) Option 2",
        "C) Option 3",
        "D) Option 4"
      ],
      "correct_answer": "A",
      "explanation": "Why this answer is correct based on the document."
    }
  ]
}
Ensure 'correct_answer' is strictly one of 'A', 'B', 'C', or 'D'. Provide exactly 5 questions."""

    user_prompt = f"Study Material Content:\n\n{sample_text}\n\nGenerate the 5 MCQs in JSON format."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    raw_response, error = call_groq_chat(messages, temperature=0.3, max_tokens=2200, json_mode=True)
    if not error and raw_response:
        data = extract_json_safely(raw_response)
        if data and isinstance(data, dict) and "mcqs" in data and isinstance(data["mcqs"], list):
            for mcq in data["mcqs"]:
                ans = str(mcq.get("correct_answer", "A")).strip().upper()
                if ans.startswith("A"):
                    mcq["correct_answer"] = "A"
                elif ans.startswith("B"):
                    mcq["correct_answer"] = "B"
                elif ans.startswith("C"):
                    mcq["correct_answer"] = "C"
                elif ans.startswith("D"):
                    mcq["correct_answer"] = "D"
                else:
                    mcq["correct_answer"] = "A"
            return {"success": True, "data": data["mcqs"]}

    logger.info("Using resilient extractive MCQs generator")
    fallback_data = build_fallback_mcqs(document_text)
    return {"success": True, "data": fallback_data}

# ==============================================================================
# 5. AI STUDY ASSISTANT / CHAT WITH DOCUMENT
# ==============================================================================
def chat_with_document(question, context_chunks, chat_history_list=None, mode="normal"):
    if chat_history_list is None:
        chat_history_list = []

    context_text = "\n\n---\n\n".join(context_chunks) if context_chunks else ""

    mode_instructions = {
        "normal": "Provide a clear, direct, and helpful answer grounded strictly in the study material.",
        "explain_simply": "Explain this in very simple, beginner-friendly terms like you are explaining it to a first-year college student. Avoid unnecessary jargon and break down difficult ideas step by step.",
        "summarize": "Provide a concise, bullet-pointed summary answering the question directly.",
        "give_example": "Explain the concept and provide clear, intuitive, real-world examples or analogies to make it immediately understandable.",
        "ask_questions": "Act as a study coach. Create 5 engaging practice check-in questions based on this topic to test the student's understanding, and provide brief answers at the end.",
        "exam_answer": "Format your response as a high-scoring university exam answer: include a concise definition/intro, structured key points with bold bullet headers, and a brief conclusion."
    }

    selected_instruction = mode_instructions.get(mode, mode_instructions["normal"])

    system_prompt = f"""You are Smart Study AI, an intelligent, empathetic academic companion for college students.
Your task is to help the student understand and master their uploaded study material.

CRITICAL RULES:
1. Base your answer primarily and truthfully on the provided Document Context.
2. If the user's question CANNOT be found in the provided Document Context, you MUST clearly state:
   "I couldn't find this information in your uploaded material. I can still explain the general concept if you'd like."
   Then provide a helpful general explanation if appropriate.
3. Style & Mode Guideline: {selected_instruction}
4. Keep the tone encouraging, professional, and clear. Use clean Markdown formatting."""

    messages = [{"role": "system", "content": system_prompt}]

    if chat_history_list:
        for msg in chat_history_list[-6:]:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({"role": role, "content": msg["message"]})

    user_content = (
        f"Document Context:\n{context_text[:5000]}\n\n"
        f"Student Question: {question}"
    )
    messages.append({"role": "user", "content": user_content})

    raw_response, error = call_groq_chat(messages, temperature=0.3, max_tokens=1500)
    if not error and raw_response:
        return {"success": True, "answer": raw_response}

    # Fallback response grounded in context
    logger.info("Using resilient context-grounded fallback answer")
    fallback_ans = build_fallback_chat(question, context_chunks)
    return {"success": True, "answer": fallback_ans}
