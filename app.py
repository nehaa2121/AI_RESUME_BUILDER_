from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3
import os
from google import genai

# TRY importing pdfkit (for local use)
try:
    import pdfkit
    PDFKIT_AVAILABLE = True
except:
    PDFKIT_AVAILABLE = False

app = Flask(__name__)
app.secret_key = "mysecretkey123"

# ---------------- AI CLIENT ----------------
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

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
            template = "functional"
        elif "designer" in job_role:
            template = "creative"
        elif "manager" in job_role:
            template = "combination"
        else:
            template = "functional"

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
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        text = response.text.strip()

        # 🔥 REMOVE unwanted parts
        if "Option" in text:
            text = text.split("Option")[0]

        return text

    except Exception as e:
        print("GEMINI ERROR:", e)
        return "Motivated graduate with strong technical skills and a passion for growth."

def ai_resume_improvement(skills, projects, experience):
    prompt = f"Improve resume:\nSkills: {skills}\nProjects: {projects}\nExperience: {experience}"
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text.strip()
    except:
        return "• Add projects\n• Use action verbs\n• Improve formatting"

def ai_skill_suggestions(skills, degree):
    prompt = f"Suggest 3 skills for {degree} with {skills}"
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
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
    
    
# ---------------- CREATE PDF ----------------
def create_pdf(data):
    data = dict(data)

    template = data.get("template")
    theme_color = data.get("theme_color")

    data.pop("template", None)
    data.pop("theme_color", None)

    rendered = render_template(
        "resume.html",
        **data,
        template=template,
        theme_color=theme_color,
        pdf_mode=True   # IMPORTANT
    )

    config = pdfkit.configuration(
        wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
    )

    options = {
        'enable-local-file-access': None,
        'page-size': 'A4',
        'margin-top': '0mm',
        'margin-right': '0mm',
        'margin-bottom': '0mm',
        'margin-left': '0mm',
        'encoding': "UTF-8"
    }

    pdfkit.from_string(
        rendered,
        "resume.pdf",
        configuration=config,
        options=options
    )

# ---------------- DOWNLOAD ----------------
@app.route("/download")
def download():
    data = session.get("user_data")

    if not data:
        return "No resume found"

    create_pdf(data)
    return send_file("resume.pdf", as_attachment=True)      

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

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)