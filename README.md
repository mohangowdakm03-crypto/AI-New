# 🤖 AI Interview Simulator

An AI-powered Interview Simulator designed for **VTU students**, providing a realistic interview experience with **technical and HR rounds**, adaptive questioning, and intelligent answer evaluation.

## Deployed link : https://neurohire-production.up.railway.app
---

## 🎯 Features

-  Semester-based question customization (VTU syllabus aligned)
-  Technical, HR, and Mixed interview modes
-  Dynamic follow-up questions (based on answer quality)
-  NLP-based answer evaluation
-  Scoring with strengths, weaknesses, and suggestions
-  Timer-based interview simulation
-  Voice input (browser-based)
-  Responsive UI (mobile + desktop)
-  Resume Assistant (optional feature)
-  Student login (Name, USN, Email)
-  Performance tracking and report generation

---

##  How It Works

1. Enter your details (Name, USN, Email)
2. Select:
   - Semester
   - Interview Mode (Technical / HR / Mixed)
3. Start interview
4. Answer questions (text or voice)
5. Get real-time feedback and final performance report

---

##  Tech Stack

- Python 
- Streamlit (UI)
- NLP-based evaluation logic
- JavaScript (for voice input & animations)

---

## ▶️ Run Locally

```bash
git clone https://github.com/mohangowdakm03-crypto/AI-Interview-Simulator
cd AI-Interview-Simulator
pip install -r requirements.txt
streamlit run app.py
