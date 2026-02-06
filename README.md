# Testing – Agents Hub

A Flask-based intelligent QA automation platform with AI-powered testing agents.

---

## Quick Start

```bash
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000** in your browser.

### Default Credentials (dev)
| Email | Password |
|---|---|
| admin@testingagents.com | Admin123! |

You can also create a new account via the **Create an Account** link on the login page.

---

## Features

### Authentication
- Login / Register with email + password
- "Remember me" persistent sessions
- Secure password hashing (Werkzeug PBKDF2)

### Agent Tree (Left Sidebar)
Agents are organised into collapsible categories:

| Category | Sub-categories / Agents |
|---|---|
| **AI-ML Testing Agents** | Data Quality Validator, Model Accuracy Tester, Bias Detection Agent |
| **Manual Testing Agents** | Test Case Generator ✦, BDD Generator, Traceability Matrix Gen, Defect Generator |
| **Functional Testing Agents** | Regression Test Planner, Smoke Test Generator |
| **Non-Functional Testing Agents** | Security (Scanner, Pen-test Planner), UI/UX (Cross-Browser, Accessibility), Compliance (GDPR, PCI-DSS) |
| **API Testing Agents** | REST API Tester, GraphQL Test Generator |
| **Test Management Agents** | Test Plan Generator, Test Report Generator |

> ✦ **Test Case Generator** is fully wired to a live LLM backend (see below). All other agents run a structured placeholder that echoes inputs; full implementations can be added incrementally.

- **Search box + Go button** – filters the tree in real time.
- **Expand All / Collapse All** – one-click tree control.
- Hover any agent to see its tooltip description.

### Workspace (Right Panel)
1. Select an agent → its required input fields appear.
2. Choose **Run Agent** or **Add to Workflow**.
3. Click **Generate / Activate**.

#### Run Agent Mode
Live output is displayed in a scrollable textarea (capped at 100 visible lines).
- **Download** – saves output as `.txt`.
- **Regenerate** – returns to the config form so you can tweak inputs or swap the document.

#### Workflow Mode
- Each selected agent is added as a node after a **START** box, connected by animated arrows.
- Click the **+** button to add more agents (select a new one in the tree first).
- Remove any agent with the **✕** badge.
- **Run Workflow** executes all agents sequentially and streams combined output.

### Settings (⚙ icon – top right)
| Section | Fields |
|---|---|
| GitHub Credentials | Username, Personal Access Token, Public Repo Path |
| LLM Configuration | Provider dropdown (Groq Free Tier, Anthropic, Google, OpenAI), Model dropdown (auto-populates), API Key |

Settings are persisted in the Flask session (cookie-based).

---

## Test Case Generator – Deep Dive

This is the first fully-implemented agent. It:

1. Accepts a **PDF, DOCX, DOC, or TXT** upload via drag-and-drop or file picker.
2. Extracts text using `pdfplumber` (PDF) or `python-docx` (Word).
3. Constructs an industry-standard prompt requesting test cases with IDs, titles, objectives, pre-conditions, steps, and expected results.
4. Calls the LLM configured in Settings (defaults to **Groq → llama-3.3-70b-versatile**).
5. Displays the response in a read-only output area.
6. Offers **Download (.txt)** and **Regenerate** actions.

### Supported LLM Providers
| Provider | Endpoint |
|---|---|
| Groq Free Tier | `https://api.groq.com/openai/v1/chat/completions` |
| OpenAI | `https://api.openai.com/v1/chat/completions` |
| Anthropic | `https://api.anthropic.com/v1/messages` |
| Google | `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` |

---

## Project Structure

```
agents_hub/
├── app.py                  # Flask app – routes, agent logic, API endpoints
├── requirements.txt        # Python dependencies
├── uploads/                # Temp storage for user-uploaded files
└── templates/
    ├── login.html          # Login page
    ├── register.html       # Registration page
    └── home.html           # Main dashboard (tree + workspace + settings modal)
```

---

## Adding a New Agent

1. Add its definition to `AGENTS_TREE` in `app.py` under the appropriate category.
2. Create a new route (e.g. `/api/agent/bdd_generate`) that builds the prompt, calls the LLM, and returns JSON `{ output }`.
3. In `home.html`, add a new conditional block inside `#agentConfig` that shows custom fields when `selectedAgentObj.id` matches.
4. Wire the `activateAgent()` function to call your new route.

---

## Design Notes
- **Dark cyber-ops theme** – deep navy backgrounds, cyan accent glows, animated grid + floating orbs on the login page.
- **Monospace code font** (Share Tech Mono) for all inputs/outputs; display font (Rajdhani) for headings.
- Fully responsive sidebar with smooth tree animations.
- All LLM calls are made server-side (Flask) so API keys are never exposed to the browser.
