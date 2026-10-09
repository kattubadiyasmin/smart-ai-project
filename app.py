import os
import re
import json
import logging
from datetime import timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, jsonify, send_file, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from database.database import (
    init_db, create_user, get_user_by_email, get_user_by_id,
    update_user_name, update_user_password, create_document,
    get_document, get_user_documents, delete_document,
    save_study_content, get_study_content, get_all_study_content_for_doc,
    add_chat_message, get_chat_history, clear_chat_history,
    save_quiz_result, get_user_quiz_results, get_dashboard_stats,
    get_user_activity_history
)
from services.pdf_service import process_and_extract_pdf, allowed_file
from services.document_service import retrieve_relevant_chunks
from services.ai_service import (
    generate_summary, generate_questions, generate_flashcards,
    generate_mcqs, chat_with_document
)
from services.export_service import generate_pdf_export

app = Flask(__name__)
app.config.from_object(Config)

# Set persistent session lifetime (7 days)
app.permanent_session_lifetime = timedelta(days=7)

# Ensure required directories exist and initialize database
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(Config.GENERATED_PDF_FOLDER, exist_ok=True)
init_db()

# ------------------------------------------------------------------------------
# Authentication & Context Helpers
# ------------------------------------------------------------------------------
def is_ajax_or_api_request():
    return (
        request.path.startswith("/api/")
        or request.path.startswith("/upload")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.is_json
        or "application/json" in request.headers.get("Accept", "")
    )

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            # If this is an AJAX or API request, NEVER return an HTML redirect page!
            if is_ajax_or_api_request():
                return jsonify({
                    "success": False,
                    "error": "Your session has expired or you are not logged in. Please log in to continue.",
                    "authenticated": False,
                    "redirect_url": url_for("login")
                }), 401
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_user():
    user = None
    if "user_id" in session:
        user = get_user_by_id(session["user_id"])
    return dict(current_user=user)

# ------------------------------------------------------------------------------
# Public Routes (Landing & Auth)
# ------------------------------------------------------------------------------
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validations
        if not name or not email or not password or not confirm_password:
            flash("All fields are required. Please fill in all information.", "error")
            return render_template("register.html", name=name, email=email)

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash("Please enter a valid email address.", "error")
            return render_template("register.html", name=name, email=email)

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return render_template("register.html", name=name, email=email)

        if password != confirm_password:
            flash("Passwords do not match. Please re-enter your password.", "error")
            return render_template("register.html", name=name, email=email)

        # Check existing email
        existing_user = get_user_by_email(email)
        if existing_user:
            flash("An account with this email already exists. Please log in.", "error")
            return redirect(url_for("login"))

        password_hash = generate_password_hash(password)
        user_id = create_user(name, email, password_hash)

        if user_id:
            session.clear()
            session.permanent = True
            session["user_id"] = user_id
            session["user_name"] = name
            session["user_email"] = email
            flash(f"Welcome to Smart Study, {name}! Your account has been created.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("An error occurred during registration. Please try again.", "error")

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please provide both email and password.", "error")
            return render_template("login.html", email=email)

        user = get_user_by_email(email)
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password. Please try again.", "error")
            return render_template("login.html", email=email)

        # Login successful
        session.clear()
        session.permanent = True
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]
        flash(f"Welcome back, {user['name']}!", "success")

        next_page = request.args.get("next")
        if next_page and next_page.startswith("/"):
            return redirect(next_page)
        return redirect(url_for("dashboard"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been safely logged out. See you next time!", "info")
    return redirect(url_for("login"))

# ------------------------------------------------------------------------------
# Dashboard & Upload
# ------------------------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    stats = get_dashboard_stats(user_id)
    recent_docs = get_user_documents(user_id)[:5]
    return render_template("dashboard.html", stats=stats, recent_docs=recent_docs)

@app.route("/upload", methods=["POST"])
@login_required
def upload_file():
    user_id = session["user_id"]
    is_ajax = is_ajax_or_api_request()

    try:
        if "file" not in request.files:
            if is_ajax:
                return jsonify({"success": False, "error": "No file uploaded. Please select a PDF file."}), 400
            flash("No file selected. Please select a PDF file.", "error")
            return redirect(url_for("dashboard"))

        file = request.files["file"]
        if file.filename == "":
            if is_ajax:
                return jsonify({"success": False, "error": "No file selected."}), 400
            flash("No file selected. Please select a PDF file.", "error")
            return redirect(url_for("dashboard"))

        # Process and extract PDF text
        result = process_and_extract_pdf(file)
        if not result["success"]:
            if is_ajax:
                return jsonify({"success": False, "error": result["error"]}), 400
            flash(result["error"], "error")
            return redirect(url_for("dashboard"))

        # Save to database
        doc_id = create_document(
            user_id=user_id,
            filename=result["filename"],
            stored_filename=result["stored_filename"],
            extracted_text=result["text"],
            file_size=result["file_size"],
            page_count=result["page_count"]
        )

        if is_ajax:
            return jsonify({
                "success": True,
                "message": "File processed successfully! Redirecting to study workspace...",
                "doc_id": doc_id,
                "redirect_url": url_for("study_workspace", doc_id=doc_id)
            })

        fname = result["filename"]
        flash(f"Successfully processed '{fname}'!", "success")
        return redirect(url_for("study_workspace", doc_id=doc_id))

    except Exception as e:
        app.logger.error(f"Error during upload: {e}", exc_info=True)
        if is_ajax:
            return jsonify({"success": False, "error": f"Failed to process file: {str(e)}"}), 500
        flash(f"An unexpected error occurred during upload: {str(e)}", "error")
        return redirect(url_for("dashboard"))

# ------------------------------------------------------------------------------
# Study Materials & History
# ------------------------------------------------------------------------------
@app.route("/materials")
@login_required
def materials():
    user_id = session["user_id"]
    docs = get_user_documents(user_id)
    return render_template("materials.html", documents=docs)

@app.route("/materials/delete/<int:doc_id>", methods=["POST"])
@login_required
def delete_material(doc_id):
    user_id = session["user_id"]
    success = delete_document(doc_id, user_id)
    if success:
        flash("Study material deleted successfully.", "success")
    else:
        flash("Unable to delete this document or access denied.", "error")
    return redirect(url_for("materials"))

@app.route("/history")
@login_required
def history():
    user_id = session["user_id"]
    activities = get_user_activity_history(user_id, limit=60)
    quiz_results = get_user_quiz_results(user_id)
    return render_template("history.html", activities=activities, quiz_results=quiz_results)

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user_id = session["user_id"]
    user = get_user_by_id(user_id)

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_name":
            name = request.form.get("name", "").strip()
            if not name:
                flash("Name cannot be empty.", "error")
            else:
                update_user_name(user_id, name)
                session["user_name"] = name
                flash("Profile name updated successfully!", "success")
            return redirect(url_for("profile"))

        elif action == "change_password":
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm_new_password = request.form.get("confirm_new_password", "")

            if not current_password or not new_password or not confirm_new_password:
                flash("All password fields are required.", "error")
                return redirect(url_for("profile"))

            if not check_password_hash(user["password_hash"], current_password):
                flash("Current password is incorrect.", "error")
                return redirect(url_for("profile"))

            if len(new_password) < 6:
                flash("New password must be at least 6 characters long.", "error")
                return redirect(url_for("profile"))

            if new_password != confirm_new_password:
                flash("New passwords do not match.", "error")
                return redirect(url_for("profile"))

            new_hash = generate_password_hash(new_password)
            update_user_password(user_id, new_hash)
            flash("Password changed successfully!", "success")
            return redirect(url_for("profile"))

    stats = get_dashboard_stats(user_id)
    return render_template("profile.html", user=user, stats=stats)

# ------------------------------------------------------------------------------
# Study Workspace
# ------------------------------------------------------------------------------
@app.route("/study/<int:doc_id>")
@login_required
def study_workspace(doc_id):
    user_id = session["user_id"]
    doc = get_document(doc_id, user_id)
    if not doc:
        flash("Document not found or you don't have permission to access it.", "error")
        return redirect(url_for("materials"))

    existing_content = get_all_study_content_for_doc(doc_id)
    word_count = len(doc["extracted_text"].split())

    return render_template(
        "study.html",
        document=doc,
        word_count=word_count,
        existing_content=existing_content
    )

# ------------------------------------------------------------------------------
# AJAX API Endpoints for AI Generation, Chat, & Quiz
# ------------------------------------------------------------------------------
@app.route("/api/content/<content_type>/<int:doc_id>", methods=["GET", "POST"])
@login_required
def get_or_generate_content(content_type, doc_id):
    try:
        user_id = session["user_id"]
        doc = get_document(doc_id, user_id)
        if not doc:
            return jsonify({"success": False, "error": "Document not found or access denied."}), 404

        if content_type not in ["summary", "questions", "flashcards", "mcqs"]:
            return jsonify({"success": False, "error": "Invalid content type."}), 400

        regenerate = request.args.get("regenerate", "false").lower() == "true" or (
            request.is_json and request.json.get("regenerate", False)
        )

        # Check if already generated
        if not regenerate:
            cached = get_study_content(doc_id, content_type)
            if cached and cached["content"]:
                try:
                    data = json.loads(cached["content"])
                    return jsonify({"success": True, "cached": True, "data": data})
                except Exception:
                    pass

        # Call AI generation service
        text = doc["extracted_text"]
        if not text or len(text.strip()) < 10:
            return jsonify({"success": False, "error": "No readable text found in this document to analyze."}), 400

        if content_type == "summary":
            result = generate_summary(text)
        elif content_type == "questions":
            result = generate_questions(text)
        elif content_type == "flashcards":
            result = generate_flashcards(text)
        elif content_type == "mcqs":
            result = generate_mcqs(text)
        else:
            return jsonify({"success": False, "error": "Unknown content type."}), 400

        if not result.get("success"):
            return jsonify({"success": False, "error": result.get("error", "AI generation failed. Please try again.")}), 500

        # Save to database
        save_study_content(doc_id, content_type, json.dumps(result["data"]))
        return jsonify({"success": True, "cached": False, "data": result["data"]})

    except Exception as e:
        app.logger.error(f"Error in get_or_generate_content: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Failed to generate {content_type}: {str(e)}"}), 500

@app.route("/api/chat/<int:doc_id>", methods=["GET", "POST"])
@login_required
def study_chat(doc_id):
    try:
        user_id = session["user_id"]
        doc = get_document(doc_id, user_id)
        if not doc:
            return jsonify({"success": False, "error": "Document not found or access denied."}), 404

        if request.method == "GET":
            history = get_chat_history(user_id, doc_id)
            chat_list = [
                {"id": row["id"], "role": row["role"], "message": row["message"], "created_at": row["created_at"]}
                for row in history
            ]
            return jsonify({"success": True, "history": chat_list})

        # POST new chat query
        data = request.get_json(silent=True) or {}
        message = data.get("message", "").strip()
        mode = data.get("mode", "normal")

        if not message:
            return jsonify({"success": False, "error": "Message cannot be empty."}), 400

        # Save user message to DB
        add_chat_message(user_id, doc_id, "user", message)

        # Retrieve relevant chunks from extracted document text
        relevant_chunks, _ = retrieve_relevant_chunks(message, doc["extracted_text"], top_k=4)

        # Fetch recent conversation context
        recent_history = get_chat_history(user_id, doc_id, limit=6)
        history_tuples = [{"role": row["role"], "message": row["message"]} for row in recent_history]

        # Call AI
        ai_result = chat_with_document(
            question=message,
            context_chunks=relevant_chunks,
            chat_history_list=history_tuples,
            mode=mode
        )

        if not ai_result.get("success"):
            return jsonify({"success": False, "error": ai_result.get("error", "AI failed to respond.")}), 500

        answer = ai_result["answer"]
        # Save assistant message to DB
        add_chat_message(user_id, doc_id, "assistant", answer)

        return jsonify({"success": True, "answer": answer, "mode": mode})

    except Exception as e:
        app.logger.error(f"Error in study_chat: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Chat service error: {str(e)}"}), 500

@app.route("/api/chat/clear/<int:doc_id>", methods=["POST"])
@login_required
def clear_chat(doc_id):
    try:
        user_id = session["user_id"]
        clear_chat_history(user_id, doc_id)
        return jsonify({"success": True, "message": "Chat history cleared."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/quiz/submit/<int:doc_id>", methods=["POST"])
@login_required
def submit_quiz(doc_id):
    try:
        user_id = session["user_id"]
        doc = get_document(doc_id, user_id)
        if not doc:
            return jsonify({"success": False, "error": "Document not found."}), 404

        payload = request.get_json(silent=True) or {}
        score = int(payload.get("score", 0))
        total_questions = int(payload.get("total_questions", 5))
        details = payload.get("details", {})

        quiz_id = save_quiz_result(user_id, doc_id, score, total_questions, details)
        return jsonify({
            "success": True,
            "quiz_id": quiz_id,
            "score": score,
            "total_questions": total_questions,
            "message": f"Quiz submitted! Your score: {score}/{total_questions}"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ------------------------------------------------------------------------------
# PDF Export Route
# ------------------------------------------------------------------------------
@app.route("/export/<content_type>/<int:doc_id>")
@login_required
def export_pdf(content_type, doc_id):
    user_id = session["user_id"]
    doc = get_document(doc_id, user_id)
    if not doc:
        abort(404, description="Document not found")

    if content_type not in ["summary", "questions", "flashcards", "mcqs", "combined"]:
        abort(400, description="Invalid export type")

    if content_type == "combined":
        raw_data = get_all_study_content_for_doc(doc_id)
        if not raw_data:
            flash("No study content generated yet to export.", "warning")
            return redirect(url_for("study_workspace", doc_id=doc_id))
    else:
        cached = get_study_content(doc_id, content_type)
        if not cached:
            flash(f"Please generate the {content_type} first before downloading PDF.", "warning")
            return redirect(url_for("study_workspace", doc_id=doc_id))
        raw_data = cached["content"]

    clean_base = re.sub(r"[^a-zA-Z0-9_-]", "_", os.path.splitext(doc["filename"])[0])
    download_filename = f"SmartStudy_{clean_base}_{content_type}.pdf"

    pdf_buffer = generate_pdf_export(content_type, doc["filename"], raw_data)
    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=download_filename
    )

# ------------------------------------------------------------------------------
# Robust Error Handlers (Always JSON for API requests)
# ------------------------------------------------------------------------------
@app.errorhandler(404)
def page_not_found(e):
    if is_ajax_or_api_request():
        return jsonify({"success": False, "error": "The requested API endpoint was not found."}), 404
    return render_template("base.html", error_title="404 - Page Not Found", error_message="The page you requested does not exist."), 404

@app.errorhandler(413)
def request_entity_too_large(e):
    if is_ajax_or_api_request():
        return jsonify({"success": False, "error": "The uploaded file is too large. Maximum allowed size is 16 MB."}), 413
    flash("The uploaded file is too large. Maximum allowed size is 16 MB.", "error")
    return redirect(url_for("dashboard"))

@app.errorhandler(500)
def server_error(e):
    if is_ajax_or_api_request():
        return jsonify({"success": False, "error": "An internal server error occurred. Please try again."}), 500
    return render_template("base.html", error_title="500 - Server Error", error_message="An internal server error occurred. Our team has been notified."), 500

@app.errorhandler(Exception)
def handle_unexpected_exception(e):
    app.logger.error(f"Unhandled Exception on {request.path}: {str(e)}", exc_info=True)
    if is_ajax_or_api_request():
        return jsonify({"success": False, "error": f"Server error: {str(e)}"}), 500
    return render_template("base.html", error_title="500 - Server Error", error_message="An unexpected error occurred. Please try again."), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
