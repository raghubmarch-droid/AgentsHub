from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
import os, json, uuid, textwrap
from datetime import timedelta
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SESSION_COOKIE_PERMANENT'] = True
app.permanent_session_lifetime = timedelta(days=30)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'doc', 'docx', 'txt'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ─── In-Memory User Store ───────────────────────────────────────────────────
users_db = {
    "admin@testingagents.com": {
        "password": generate_password_hash("Admin123!"),
        "name": "Admin User"
    }
}

# ─── Agent Definitions ──────────────────────────────────────────────────────
AGENTS_TREE = {
    "AI-ML Testing Agents": [
        {"id": "aiml_data_quality",    "name": "Data Quality Validator",      "desc": "Validates ML training/test dataset quality and flags issues like missing values, class imbalance, and data drift."},
        {"id": "aiml_model_test",      "name": "Model Accuracy Tester",       "desc": "Evaluates ML model performance using accuracy, precision, recall and F1 metrics against gold-standard datasets."},
        {"id": "aiml_bias_detect",     "name": "Bias Detection Agent",        "desc": "Scans ML models for demographic and algorithmic biases across protected attributes."}
    ],
    "Manual Testing Agents": [
        {"id": "manual_tc_gen",        "name": "Test Case Generator",         "desc": "Generates industry-standard manual test cases from uploaded requirements documents (PDF/Word) using AI."},
        {"id": "manual_bdd_gen",       "name": "BDD Generator",              "desc": "Converts requirements into Behavior-Driven Development scenarios in Gherkin syntax (Given/When/Then)."},
        {"id": "manual_trace_matrix",  "name": "Traceability Matrix Gen",    "desc": "Creates a requirements traceability matrix (RTM) mapping each requirement to corresponding test cases."},
        {"id": "manual_defect_gen",    "name": "Defect Generator",           "desc": "Generates detailed defect reports from test session notes with severity, priority, and reproduction steps."}
    ],
    "Functional Testing Agents": [
        {"id": "func_regression",      "name": "Regression Test Planner",    "desc": "Plans and prioritises regression test suites based on recent code changes and historical failure data."},
        {"id": "func_smoke",           "name": "Smoke Test Generator",       "desc": "Creates quick smoke-test scripts that cover critical user paths after every build deployment."}
    ],
    "Non-Functional Testing Agents": {
        "Security Testing Agents": [
            {"id": "nf_sec_scan",      "name": "Security Vulnerability Scanner", "desc": "Performs OWASP-based security scanning of code-base / API endpoints for common vulnerabilities."},
            {"id": "nf_sec_pen",       "name": "Penetration Test Planner",       "desc": "Designs penetration-test plans targeting web apps, APIs, and internal networks."}
        ],
        "UI/UX Testing Agents": [
            {"id": "nf_uiux_compat",   "name": "Cross-Browser Compatibility",   "desc": "Tests UI rendering and behaviour across Chrome, Firefox, Safari, and Edge."},
            {"id": "nf_uiux_access",   "name": "Accessibility Auditor",         "desc": "Audits pages against WCAG 2.1 guidelines and reports accessibility issues."}
        ],
        "Compliance Testing Agents": [
            {"id": "nf_comp_gdpr",     "name": "GDPR Compliance Checker",       "desc": "Validates application handling of PII data against GDPR regulations."},
            {"id": "nf_comp_pci",      "name": "PCI-DSS Auditor",               "desc": "Checks payment-card data handling flows for PCI-DSS compliance."}
        ]
    },
    "API Testing Agents": [
        {"id": "api_rest",             "name": "REST API Tester",             "desc": "Auto-generates and executes REST API test suites from OpenAPI/Swagger specs."},
        {"id": "api_graphql",          "name": "GraphQL Test Generator",     "desc": "Generates mutation and query tests for GraphQL endpoints."}
    ],
    "Test Management Agents": [
        {"id": "tm_plan",              "name": "Test Plan Generator",        "desc": "Drafts end-to-end test plans including scope, strategy, schedule and resource allocation."},
        {"id": "tm_report",            "name": "Test Report Generator",     "desc": "Compiles test session results into executive-ready reports with charts and KPIs."}
    ]
}

LLM_OPTIONS = [
    {"provider": "Groq Free Tier", "models": [
        "llama-3.3-70b-versatile",
        "mixtral-8x7b-32768",
        "gemma2-9b-it"
    ]},
    {"provider": "Anthropic", "models": ["claude-3-5-sonnet", "claude-3-opus", "claude-3-haiku"]},
    {"provider": "Google",    "models": ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.0-pro"]},
    {"provider": "OpenAI",    "models": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]}
]

# ─── Helpers ─────────────────────────────────────────────────────────────────
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text_from_file(filepath):
    """Extract raw text from uploaded file (simplified – production would use pdfplumber / python-docx)."""
    ext = filepath.rsplit('.', 1)[1].lower()
    try:
        if ext == 'txt':
            with open(filepath, 'r', errors='ignore') as f:
                return f.read()
        elif ext in ('doc', 'docx'):
            try:
                import docx
                doc = docx.Document(filepath)
                return '\n'.join([p.text for p in doc.paragraphs])
            except ImportError:
                with open(filepath, 'r', errors='ignore') as f:
                    return f.read()
        elif ext == 'pdf':
            try:
                import pdfplumber
                text = ''
                with pdfplumber.open(filepath) as pdf:
                    for page in pdf.pages:
                        text += (page.extract_text() or '') + '\n'
                return text
            except ImportError:
                return "[PDF text extraction requires pdfplumber – install via: pip install pdfplumber]"
    except Exception as e:
        return f"[Error reading file: {e}]"
    return ""

# ─── Auth Routes ─────────────────────────────────────────────────────────────
@app.route('/', methods=['GET'])
def index():
    if session.get('logged_in'):
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    email    = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    remember = request.form.get('remember') == 'on'

    user = users_db.get(email)
    if user and check_password_hash(user['password'], password):
        session['logged_in'] = True
        session['email']     = email
        session['name']      = user['name']
        session.permanent    = remember
        return redirect(url_for('home'))
    return render_template('login.html', error="Invalid email or password.")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        if not all([name, email, password]):
            return render_template('register.html', error="All fields are required.")
        if password != confirm:
            return render_template('register.html', error="Passwords do not match.")
        if email in users_db:
            return render_template('register.html', error="Email already registered.")
        users_db[email] = {"password": generate_password_hash(password), "name": name}
        session['logged_in'] = True
        session['email']     = email
        session['name']      = name
        return redirect(url_for('home'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ─── Home ────────────────────────────────────────────────────────────────────
@app.route('/home')
def home():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    return render_template('home.html', agents=AGENTS_TREE, llm_options=LLM_OPTIONS)

# ─── Settings (AJAX) ─────────────────────────────────────────────────────────
@app.route('/api/settings', methods=['GET', 'POST'])
def settings_api():
    if request.method == 'POST':
        data = request.get_json(force=True)
        session['github_username']  = data.get('github_username', '')
        session['github_token']     = data.get('github_token', '')
        session['github_repo']      = data.get('github_repo', '')
        session['llm_provider']     = data.get('llm_provider', '')
        session['llm_model']        = data.get('llm_model', '')
        session['llm_api_key']      = data.get('llm_api_key', '')
        session.modified = True
        return jsonify({"status": "saved"})
    return jsonify({
        "github_username": session.get('github_username', ''),
        "github_token":    session.get('github_token', ''),
        "github_repo":     session.get('github_repo', ''),
        "llm_provider":    session.get('llm_provider', ''),
        "llm_model":       session.get('llm_model', ''),
        "llm_api_key":     session.get('llm_api_key', '')
    })

# ─── Upload Requirements Doc ─────────────────────────────────────────────────
@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    f = request.files['file']
    if f.filename == '':
        return jsonify({"error": "No file selected"}), 400
    if not allowed_file(f.filename):
        return jsonify({"error": "Unsupported file type. Use PDF, DOC, DOCX, or TXT."}), 400
    uid = str(uuid.uuid4())
    safe = secure_filename(f.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], uid + '_' + safe)
    f.save(path)
    session['last_upload_path']  = path
    session['last_upload_name']  = f.filename
    session.modified = True
    return jsonify({"status": "uploaded", "filename": f.filename, "path": path})

# ─── Test Case Generator – the live agent ───────────────────────────────────
@app.route('/api/agent/tc_generate', methods=['POST'])
def tc_generate():
    data          = request.get_json(force=True)
    custom_prompt = data.get('custom_prompt', '').strip()
    upload_path   = data.get('upload_path') or session.get('last_upload_path')

    if not upload_path or not os.path.exists(upload_path):
        return jsonify({"error": "No requirements document uploaded."}), 400

    api_key  = session.get('llm_api_key', '').strip()
    provider = session.get('llm_provider', '')
    model    = session.get('llm_model', 'llama-3.3-70b-versatile')

    if not api_key:
        return jsonify({"error": "API key not configured. Open Settings and enter your LLM API key."}), 400

    # Extract text
    req_text = extract_text_from_file(upload_path)
    if not req_text.strip():
        return jsonify({"error": "Could not extract text from the uploaded document."}), 400

    # Build prompt
    base_prompt = (
        "You are a senior QA engineer. Based on the following requirements document, "
        "generate a comprehensive set of manual test cases in industry-standard format.\n\n"
        "Each test case must include:\n"
        "- Test Case ID\n"
        "- Test Case Title\n"
        "- Objective\n"
        "- Pre-conditions\n"
        "- Test Steps (numbered)\n"
        "- Expected Results\n"
        "- Actual Results (leave blank)\n"
        "- Status (leave as 'Not Executed')\n\n"
        "Requirements Document:\n"
        "---\n"
        f"{req_text}\n"
        "---\n\n"
        "Generate at least 10 thorough test cases covering positive, negative, and edge-case scenarios."
    )
    if custom_prompt.strip():
        base_prompt += f"\n\nAdditional instructions from user:\n{custom_prompt}"

    # Call Groq / provider API
    try:
        import requests as req_lib
        if provider == "Groq Free Tier":
            url     = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": base_prompt}],
                "max_tokens": 4096,
                "temperature": 0.3
            }
        elif provider == "OpenAI":
            url     = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": base_prompt}],
                "max_tokens": 4096,
                "temperature": 0.3
            }
        elif provider == "Anthropic":
            url     = "https://api.anthropic.com/v1/messages"
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": base_prompt}]
            }
        elif provider == "Google":
            url     = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {"contents": [{"parts": [{"text": base_prompt}]}]}
        else:
            return jsonify({"error": "Unsupported provider."}), 400

        resp = req_lib.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        resp_json = resp.json()

        # Parse response based on provider
        if provider in ("Groq Free Tier", "OpenAI"):
            output = resp_json["choices"][0]["message"]["content"]
        elif provider == "Anthropic":
            output = resp_json["content"][0]["text"]
        elif provider == "Google":
            output = resp_json["candidates"][0]["content"]["parts"][0]["text"]
        else:
            output = str(resp_json)

        return jsonify({"status": "success", "output": output})

    except Exception as e:
        return jsonify({"error": f"LLM call failed: {str(e)}"}), 500

# ─── Penetration-Test Planner ────────────────────────────────────────────────
@app.route('/api/agent/pentest_plan', methods=['POST'])
def pentest_plan():
    data         = request.get_json(force=True)
    scope        = data.get('scope', 'all').strip()          # web | api | network | all
    target       = data.get('target', '').strip()            # URL / IP / CIDR
    extra_notes  = data.get('extra_notes', '').strip()

    # ── pull LLM config from session ──
    api_key  = session.get('llm_api_key', '').strip()
    provider = session.get('llm_provider', '')
    model    = session.get('llm_model', 'llama-3.3-70b-versatile')

    if not api_key:
        return jsonify({"error": "API key not configured. Open Settings and enter your LLM API key."}), 400
    if not target:
        return jsonify({"error": "Target URL / IP / CIDR is required."}), 400

    # ── scope label for the prompt ──
    scope_labels = {
        "web":     "Web Application",
        "api":     "API (REST / GraphQL / gRPC)",
        "network": "Internal Network",
        "all":     "Web Application, API, and Internal Network"
    }
    scope_text = scope_labels.get(scope, "Web Application, API, and Internal Network")

    # ── Kali-tool & Metasploit reference block (injected once, LLM maps to phases) ──
    kali_tools_ref = """
KALI LINUX TOOL CATALOGUE – map every phase to at least one tool from this list:
  Reconnaissance   : nmap, theHarvester, shodan (CLI), maltego, recon-ng, whois, dig, traceroute, amass
  Scanning         : nmap (--sV -sC -sU), OpenVAS / GVM, Nikto, gobuster, dirb, feroxbuster, wfuzz
  Web-App          : Burp Suite Pro, OWASP ZAP, sqlmap, Hydra, Medusa, Commix, XSStrike, eyewitness
  API              : Postman (manual), OWASP ZAP (API mode), sqlmap (--dbs), Burp Suite (replay), jwt_tool, wfuzz
  Network / Infra  : Wireshark, tcpdump, Responder, Impacket (ntlmrelayx, secretsdump), CrackMapExec, BloodHound, enum4linux
  Exploitation     : Metasploit Framework (msfconsole), msfvenom (payload generation)
  Post-Exploitation: Metasploit (post modules), Mimikatz (via Impacket or meterpreter), LinPEAS, WinPEAS
  Reporting        : Faraday, Dradis, or manual report
"""

    msf_ref = """
METASPLOIT MODULE & PAYLOAD CATALOGUE – for every exploitation / post-exploitation step select the
most relevant modules and payloads from this reference.  Include the exact 'use' path.

  ── Web-App Exploitation ──
  use exploit/multi/handler                          (generic listener)
  use auxiliary/scanner/http/http_title              (web-app recon)
  use auxiliary/scanner/http/http_sql_injection      (SQLi detection)
  use exploit/webapps/tomcat/http_put                (Tomcat PUT upload)
  use exploit/webapps/tomcat/apache_tomcat_text      (default creds)
  use exploit/multi/http/struts2_code_exec_s2_045    (Struts2 RCE)
  use exploit/multi/http/wp_pingback_xxe             (WordPress XXE)
  use exploit/multi/http/jenkins_ci_script_console   (Jenkins RCE)

  ── API / Service Exploitation ──
  use auxiliary/scanner/http/http_api_sqli           (API SQLi scan)
  use exploit/multi/http/php_info_xmlrpc             (XML-RPC / PHP-FPM)
  use exploit/multi/http/grafana_ssrf                (Grafana SSRF)

  ── Network / Infrastructure ──
  use auxiliary/scanner/smb/smb_ms17_010             (EternalBlue check)
  use exploit/windows/smb/ms17_010_eternalblue       (EternalBlue RCE)
  use exploit/windows/smb/ms08_067_netapi            (NetAPI RCE)
  use exploit/windows/mssql/mssql_payload            (MSSQL xp_cmdshell)
  use exploit/linux/samba/is_not_a_virus             (Samba RCE)
  use auxiliary/scanner/ssh/ssh_enumusers            (SSH user-enum)
  use exploit/linux/ssh/ssh_user_enum_timing         (timing attack)
  use exploit/windows/http/iis_xcopy                 (IIS file upload)
  use exploit/multi/misc/openssl_chm_rce             (OpenSSL heartbleed)

  ── Common Payloads (msfvenom) ──
  windows/x64/meterpreter/reverse_tcp
  windows/x64/meterpreter_reverse_tcp               (staged vs stageless)
  linux/x64/meterpreter/reverse_tcp
  php/meterpreter/reverse_tcp
  java/meterpreter/reverse_tcp
  cmd/powershell_reverse_tcp

  ── Post-Exploitation ──
  use post/windows/gather/credentials/credential_collector
  use post/windows/manage/shell_to_meterpreter
  use post/multi/recon/local_exploit_suggester
  use post/linux/gather/local_exploit_suggester
  use post/windows/gather/hashdump
  use post/linux/gather/hashdump
"""

    # ── assemble the master prompt ──
    system_prompt = (
        "You are a seasoned offensive-security professional and certified penetration tester "
        "(OSCP / PNPT level). Your task is to produce a comprehensive, phase-by-phase penetration-test "
        "plan in a structured, professional report format.\n\n"
        "RULES:\n"
        "1. Every phase MUST list at least one Kali Linux tool with the exact CLI flags or options you "
        "   would use.\n"
        "2. Every exploitation and post-exploitation step MUST reference at least one Metasploit module "
        "   (full 'use' path) and, where applicable, a msfvenom payload.\n"
        "3. Map attack vectors to MITRE ATT&CK Technique IDs (e.g. T1190, T1078).\n"
        "4. For each phase include: Objective, Tools + exact usage, Attack Vectors / Payloads "
        "   (with Metasploit paths), Expected Outcome, and Risk Rating (Critical / High / Medium / Low).\n"
        "5. Close with a prioritised remediation checklist.\n"
        "6. Use the reference catalogues below verbatim — do NOT invent tool names or module paths.\n\n"
        + kali_tools_ref + "\n"
        + msf_ref
    )

    user_prompt = (
        f"TARGET SCOPE : {scope_text}\n"
        f"TARGET        : {target}\n\n"
        "Generate the full penetration-test plan now.\n\n"
    )
    if extra_notes.strip():
        user_prompt += f"ADDITIONAL CONTEXT FROM TESTER:\n{extra_notes}\n\n"

    user_prompt += (
        "Structure your plan with these top-level sections:\n"
        "  1. Engagement Overview (rules of engagement assumptions, disclaimer)\n"
        "  2. Reconnaissance & Information Gathering\n"
        "  3. Scanning & Enumeration\n"
        "  4. Vulnerability Assessment\n"
        "  5. Exploitation\n"
        "  6. Post-Exploitation & Lateral Movement\n"
        "  7. Data Exfiltration & Persistence (theoretical / scoped)\n"
        "  8. Reporting & Remediation\n\n"
        "Be thorough. Each section should have multiple sub-steps."
    )

    # ── dispatch to the LLM ──
    try:
        import requests as req_lib

        if provider == "Groq Free Tier":
            url     = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt}
                ],
                "max_tokens": 8192,
                "temperature": 0.25
            }
        elif provider == "OpenAI":
            url     = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt}
                ],
                "max_tokens": 8192,
                "temperature": 0.25
            }
        elif provider == "Anthropic":
            url     = "https://api.anthropic.com/v1/messages"
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
            # Anthropic has no 'system' key in messages; use the top-level system param
            payload = {
                "model":  model,
                "system": system_prompt,
                "max_tokens": 8192,
                "messages": [{"role": "user", "content": user_prompt}]
            }
        elif provider == "Google":
            # Google Gemini – merge system + user into one text block
            combined = system_prompt + "\n\n---\n\n" + user_prompt
            url     = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {"contents": [{"parts": [{"text": combined}]}]}
        else:
            return jsonify({"error": "Unsupported LLM provider."}), 400

        resp = req_lib.post(url, headers=headers, json=payload, timeout=180)
        resp.raise_for_status()
        resp_json = resp.json()

        # ── parse response ──
        if provider in ("Groq Free Tier", "OpenAI"):
            output = resp_json["choices"][0]["message"]["content"]
        elif provider == "Anthropic":
            output = resp_json["content"][0]["text"]
        elif provider == "Google":
            output = resp_json["candidates"][0]["content"]["parts"][0]["text"]
        else:
            output = str(resp_json)

        return jsonify({"status": "success", "output": output})

    except Exception as e:
        return jsonify({"error": f"LLM call failed: {str(e)}"}), 500

# ─── Download generated output ──────────────────────────────────────────────
@app.route('/api/download', methods=['POST'])
def download_output():
    data     = request.get_json(force=True)
    content  = data.get('content', '')
    filename = data.get('filename', 'output.txt')
    path     = os.path.join(app.config['UPLOAD_FOLDER'], 'dl_' + secure_filename(filename))
    with open(path, 'w') as f:
        f.write(content)
    return send_file(path, as_attachment=True, download_name=filename)

# ─── Generic agent activation stub (for non-implemented agents) ──────────────
@app.route('/api/agent/run', methods=['POST'])
def run_agent_generic():
    data      = request.get_json(force=True)
    agent_id  = data.get('agent_id', '')
    inputs    = data.get('inputs', {})
    # Simulate streaming output for demonstration
    lines = [
        f"[{agent_id}] Agent initialised …",
        f"[{agent_id}] Connecting to LLM: {session.get('llm_model', 'N/A')} …",
        f"[{agent_id}] Reading inputs …"
    ]
    for k, v in inputs.items():
        lines.append(f"[{agent_id}]   {k}: {v}")
    lines.append(f"[{agent_id}] Processing …")
    lines.append(f"[{agent_id}] ⚠ This agent is a placeholder. Full implementation coming soon.")
    lines.append(f"[{agent_id}] Done.")
    return jsonify({"status": "success", "output": "\n".join(lines)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5090)
