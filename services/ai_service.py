import os
import json
import re
from groq import Groq
from config import Config

# Primary and fallback models known to work with current Groq API
DEFAULT_MODELS = [
    Config.GROQ_MODEL,
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant"
]

def get_groq_client():
    api_key = Config.GROQ_API_KEY or os.environ.get("GROQ_API_KEY", "")
    if not api_key or api_key == "your_groq_api_key_here":
        return None
    return Groq(api_key=api_key)

def call_groq_chat(messages, temperature=0.3, max_tokens=2500, json_mode=False):
    """
    Calls Groq chat completion with automatic model fallback and error handling.
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
        try:
            kwargs = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            
            response = client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            content = choice.message.content
            if content and content.strip():
                return content.strip(), None
        except Exception as e:
            err_msg = str(e)
            if "model_decommissioned" in err_msg or "model_not_found" in err_msg or "404" in err_msg:
                continue
            if "401" in err_msg or "invalid_api_key" in err_msg:
                return None, "Invalid Groq API Key. Please verify your GROQ_API_KEY in .env."
            if "429" in err_msg or "rate_limit" in err_msg:
                return None, "Groq API rate limit reached. Please wait a moment and try again."
            continue

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

# ==============================================================================
# 1. SUMMARY GENERATION
# ==============================================================================
def generate_summary(document_text):
    sample_text = document_text[:18000]

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

    raw_response, error = call_groq_chat(messages, temperature=0.2, json_mode=True)
    if error:
        return {"success": False, "error": error}

    data = extract_json_safely(raw_response)
    if not data or not isinstance(data, dict):
        return {
            "success": True,
            "data": {
                "overview": raw_response or "Summary generated.",
                "key_concepts": [],
                "important_points": [],
                "exam_focused_points": [],
                "revision_notes": []
            }
        }

    return {"success": True, "data": data}

# ==============================================================================
# 2. IMPORTANT QUESTIONS GENERATION
# ==============================================================================
def generate_questions(document_text):
    sample_text = document_text[:18000]

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

    raw_response, error = call_groq_chat(messages, temperature=0.3, json_mode=True)
    if error:
        return {"success": False, "error": error}

    data = extract_json_safely(raw_response)
    if data and isinstance(data, dict) and "questions" in data and isinstance(data["questions"], list):
        return {"success": True, "data": data["questions"]}
    elif data and isinstance(data, list):
        return {"success": True, "data": data}
    
    return {
        "success": False,
        "error": "Failed to generate structured questions. Please try again."
    }

# ==============================================================================
# 3. FLASHCARDS GENERATION
# ==============================================================================
def generate_flashcards(document_text):
    sample_text = document_text[:18000]

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

    raw_response, error = call_groq_chat(messages, temperature=0.3, json_mode=True)
    if error:
        return {"success": False, "error": error}

    data = extract_json_safely(raw_response)
    if data and isinstance(data, dict) and "flashcards" in data and isinstance(data["flashcards"], list):
        return {"success": True, "data": data["flashcards"]}
    elif data and isinstance(data, list):
        return {"success": True, "data": data}

    return {
        "success": False,
        "error": "Failed to generate structured flashcards. Please try again."
    }

# ==============================================================================
# 4. MCQ QUIZ GENERATION
# ==============================================================================
def generate_mcqs(document_text):
    sample_text = document_text[:18000]

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

    raw_response, error = call_groq_chat(messages, temperature=0.3, json_mode=True)
    if error:
        return {"success": False, "error": error}

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

    return {
        "success": False,
        "error": "Failed to generate structured MCQs. Please try again."
    }

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
        f"Document Context:\n{context_text}\n\n"
        f"Student Question: {question}"
    )
    messages.append({"role": "user", "content": user_content})

    raw_response, error = call_groq_chat(messages, temperature=0.3, max_tokens=1500)
    if error:
        return {"success": False, "error": error}

    return {"success": True, "answer": raw_response}
