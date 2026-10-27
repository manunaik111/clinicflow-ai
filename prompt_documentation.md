# Prompt Documentation: ClinicFlow AI

This document lists the prompts I used while developing ClinicFlow AI, in the order I used them, including corrections and follow-ups that improved the results.

- **Project:** ClinicFlow AI, a healthcare patient-request triage automation
- **Assessment:** AI Skills & Prompt Engineering Assessment (Task 1)
- **Main AI tool for planning and building:** Claude (claude.ai chat)
- **Prompts are quoted exactly as I typed them**, including typing mistakes.

---

## How I worked with the AI

1. I gave the AI the assignment PDF and asked what to do and why, so I understood the task before building anything.
2. I asked for a project plan, then approved it.
3. I set strict working rules: build one file at a time, explain every file, and never change the plan without asking me first.
4. After each file I reviewed the explanation, then moved on with a short prompt.
5. When the AI misunderstood a requirement, I corrected it with a follow-up prompt, and the output changed.

---

## Part A: Prompts I used to build the project

### Prompt 1: Understanding the assignment
- **Stage:** Planning
- **Tool:** Claude
- **My prompt:**
  > this is my assignment can you tell me what to do and why do i need to select that
- **What I attached:** The assignment PDF.
- **Result:** The AI summarised the task and the three required submissions, compared the five project areas, and recommended Automation or Innovation in healthcare because it fits my background in backend APIs, chatbots, and RAG. It also pointed out a few cautions about the company and the web scraping option.
- **Why I wrote it this way:** I wanted to understand the requirements and the reason behind the choice, not just get an answer.

### Prompt 2: Asking for a project to build
- **Stage:** Planning
- **Tool:** Claude
- **My prompt:**
  > make sure we built the project that i get selected to next process of shrtlisiting so help me
- **Result:** The AI proposed ClinicFlow AI, a healthcare triage automation, with a stack (FastAPI, LangGraph, Gemini and Claude, Streamlit, SQLite), a build plan, a prompt-documentation approach, and a video outline.
- **Decision:** I chose to go ahead with this project.

### Prompt 3: Setting the working rules
- **Stage:** Planning and process control
- **Tool:** Claude
- **My prompt:**
  > do it one file at a time and exaplin everything about that file and do not change the plan without asking me before hand make sure you are doing what iam asking
- **Result:** The AI started building one file at a time and explained the file's purpose, structure, and reasons. It also asked for approval before moving to the next file or making a design choice.
- **Why this matters:** Without these rules the AI could build everything at once, and I would not understand it well enough to explain it in my video.

### Prompt 4: Continue to the next file
- **Stage:** Build, data
- **Tool:** Claude
- **My prompt:**
  > next
- **Result:** Created `data/test_messages.json`, 36 labelled synthetic patient messages, including hard cases such as urgent symptoms hidden in a polite booking request.

### Prompt 5: Continue to the next file
- **Stage:** Build, setup
- **Tool:** Claude
- **My prompt:**
  > next
- **Result:** Created `requirements.txt`. The AI also raised a design choice (Gemini embeddings plus simple numpy search instead of a separate vector database) and asked whether I agreed.

### Prompt 6: Two files together
- **Stage:** Build, setup
- **Tool:** Claude
- **My prompt:**
  > next both file
- **Result:** Created `.env.example` and `.gitignore`, so API keys stay private and are never uploaded to GitHub.

### Prompt 7: Approving the prompts file
- **Stage:** Build, prompts
- **Tool:** Claude
- **My prompt:**
  > yes
- **Result:** Created `app/prompts.py`, with version 1 of the app's internal prompts (classify, extract, FAQ answer, draft reply, escalate), stored by version so accuracy can be compared across versions.

### Prompt 8: Correcting a misunderstanding (revision)
- **Stage:** Process correction
- **Tool:** Claude
- **My prompt:**
  > no no you got it worng about prompt documentation read it agian
- **What was wrong:** The AI had said the prompt documentation should contain the prompts inside the app. The assignment actually asks for the prompts **I used to develop the project**, meaning my own prompts to AI tools.
- **Result:** The AI re-read the requirement, admitted the mistake, and explained the correct structure: my own prompts first, with the app's internal prompts only as an optional appendix.
- **What I learned:** Checking the AI's reading of the source requirement is worth doing. A short, direct correction was enough to fix it.

### Prompt 9: Asking for this document
- **Stage:** Documentation
- **Tool:** Claude
- **My prompt:**
  > prompt_documentation.md first create this
- **Result:** Created this file, with a template for logging future prompts and the prompts above already recorded.

<!-- Add new entries below. Copy the template at the bottom of this file. -->

---

## Part B: Prompts used inside the app (appendix)

These are the prompts that ClinicFlow AI itself sends to Gemini and Claude when it processes a patient message. They live in `app/prompts.py` and are versioned so the same test set can be run against each version.

| Version | Status | Notes |
|---|---|---|
| v1 | Written (baseline) | Simple, with no role, rules, or examples. Used to see where the system fails. |
| v2 | Not written yet | To be added after testing v1 |
| v3 | Not written yet | To be added after testing v2 |

### Accuracy results by version
| Version | Classification accuracy (36 test messages) | Main failures observed | Changes made next |
|---|---|---|---|
| v1 | (to fill after testing) | | |
| v2 | | | |
| v3 | | | |

---

## Entry template (copy for each new prompt)

### Prompt N: Short title
- **Stage:** (planning, build, debugging, testing, documentation, deployment)
- **Tool:** (Claude, Gemini, other)
- **My prompt:**
  > (exact text)
- **What I attached or provided:** (files, error messages, if any)
- **Result:** (what the AI produced, in one or two sentences)
- **Problem or revision:** (what was wrong or could be better, and what I changed in my next prompt)
- **What I learned:** (optional)
