from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3
import os
import google.generativeai as genai

# TRY importing pdfkit (for local use)
try:
    import pdfkit
    PDFKIT_AVAILABLE = True
except:
    PDFKIT_AVAILABLE = False

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback")

# ---------------- AI CLIENT ----------------
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# ---------------- DATABASE INIT ----------------
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS resumes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        phone TEXT,
        address TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("index.html")

# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (name, email, password) VALUES (?,?,?)",
                (name, email, password)
            )
            conn.commit()
        except:
            return "User already exists!"

        conn.close()
        return redirect("/login")

    return render_template("signup.html")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, password)
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            session["user"] = user[0]   # FIXED
            return redirect("/dashboard")
        else:
            return "Invalid Email or Password"

    return render_template("login.html")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM resumes")
    resumes = cursor.fetchall()

    conn.close()
    return render_template("dashboard.html", resumes=resumes)

# ---------------- TEMPLATES ----------------
@app.route("/templates")
def templates():
    return render_template("templates.html")

# ---------------- AUTO GENERATE ----------------
@app.route('/auto_generate', methods=['GET', 'POST'])
def auto_generate():
    if request.method == 'POST':
        job_role = request.form.get('job_role', "").lower()

        if "developer" in job_role:
            template = "chronological"
        elif "student" in job_role:
            template = "elegant_gray"
        elif "designer" in job_role:
            template = "creative_resume"
        elif "manager" in job_role:
            template = "combination_resume"
        else:
            template = "simple"

        return redirect(f'/form?template={template}')

    return render_template('auto_generate.html')

# ---------------- FORM ----------------
@app.route('/form')
def form():
    template = request.args.get('template') or "chronological"
    return render_template('form.html', template=template)

# ---------------- AI FUNCTIONS ----------------
def generate_summary(skills, degree):
    skills = skills or "general skills"
    degree = degree or "graduate"

    prompt = f"""
Write ONLY a 3-line professional resume summary.

NO options.
NO extra text.
NO headings.
ONLY final answer.

Degree: {degree}
Skills: {skills}
"""

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")

        response = model.generate_content(prompt)

        text = response.text.strip()

        # 🔥 REMOVE unwanted parts
        if "Option" in text:
            text = text.split("Option")[0]

        return text

    except Exception as e:
        print("GEMINI ERROR:", e)
        return "Motivated graduate with strong technical skills and a passion for growth."

def ai_resume_improvement(skills, projects, experience):
    prompt = f"""
You are an AI resume tool.

Give VERY SHORT output.

Rules:
- Only 4 bullet points
- Max 6 words per point
- No explanation
- No extra text
- No headings

Resume:
Skills: {skills}
Projects: {projects}
Experience: {experience}

Output:
• ...
• ...
• ...
• ...
"""
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")

        response = model.generate_content(prompt)

        text = response.text.strip()

        # 🔥 EXTRA SAFETY CUT (IMPORTANT)
        lines = text.split("\n")
        short_output = "\n".join(lines[:4])

        return short_output

    except:
        return "• Add projects\n• Use action verbs\n• Improve skills\n• Clean format"

def ai_skill_suggestions(skills, degree):
    prompt = f"Suggest 3 skills for {degree} with {skills}"
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")

        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return "Communication, Problem-solving, Teamwork"

# ---------------- GENERATE RESUME ----------------
@app.route("/generate_resume", methods=["POST"])
def generate_resume():
    data = request.form.to_dict()

    template = data.get("template") or "chronological"
    theme_color = data.get("theme_color")

    data.pop("template", None)
    data.pop("theme_color", None)

    ai_summary = generate_summary(data.get("skills"), data.get("degree"))
    ai_output = ai_resume_improvement(
        data.get("skills"),
        data.get("projects"),
        data.get("experience")
    )
    ai_skills = ai_skill_suggestions(
        data.get("skills"),
        data.get("degree")
    )

    # SAVE TO SESSION
    session["user_data"] = {
        **data,
        "template": template,
        "theme_color": theme_color,
        "ai_summary": ai_summary
    }

    return render_template(
        "resume.html",
        **data,
        template=template,
        theme_color=theme_color,
        ai_summary=ai_summary,
        ai_output=ai_output,
        ai_skills=ai_skills
    )
    

# ---------------- AI ANALYSIS ----------------
@app.route("/ai_analysis")
def ai_analysis():
    data = session.get("user_data")

    if not data:
        return "No data found. Please generate resume first."

    skills = data.get("skills")
    projects = data.get("projects")
    experience = data.get("experience")
    degree = data.get("degree")

    ai_output = ai_resume_improvement(skills, projects, experience)
    ai_skills = ai_skill_suggestions(skills, degree)

    return render_template(
        "ai_analysis.html",
        ai_output=ai_output,
        ai_skills=ai_skills,
        suggestions=[
            "Add more projects",
            "Use strong action verbs",
            "Improve formatting"
        ]
    )
    
# ---------------- DOWNLOAD PDF ----------------
@app.route("/download")
def download():
    if not PDFKIT_AVAILABLE:
        return "PDF download not supported on server yet"

    data = session.get("user_data")

    if not data:
        return "No resume found"

    template = data.get("template", "simple")

    template_map = {
        "simple": "simple.html",
        "modern_blue": "modern_blue.html",
        "modern_dark": "modern_dark.html",
        "card_ui": "card_ui.html",
        "bold_red": "bold_red.html",
        "professional_green": "professional_green.html",
        "classic_resume": "classic_resume.html",
        "creative_gradient": "creative_gradient.html",
        "elegant_gray": "elegant_gray.html",
        "minimal_white": "minimal_white.html",
        "chronological": "chronological.html",
        "creative": "creative.html",
        "combination": "combination.html"
    }

    selected_template = template_map.get(template, "simple.html")

    rendered_html = render_template(
        selected_template,
        **data,
        pdf_mode=True
    )

    options = {
        'page-size': 'A4',
        'margin-top': '0mm',
        'margin-right': '0mm',
        'margin-bottom': '0mm',
        'margin-left': '0mm',
        'encoding': "UTF-8",
        'enable-local-file-access': None
    }

    pdfkit.from_string(rendered_html, "resume.pdf", options=options)

    return send_file("resume.pdf", as_attachment=True)

"""config = pdfkit.configuration(
    wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
)
"""

    

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run()