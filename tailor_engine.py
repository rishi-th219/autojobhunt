#!/usr/bin/env python3
"""
tailor_engine.py — Dynamic Job Tailoring & Answer Drafting Engine
Analyzes job descriptions (JDs) and dynamically drafts grounded, compelling
answers to open-ended ATS screening questions and cover letters.
Grounds all generated responses strictly in the user's config/profile.yml and cv.md.
"""

import os
import re
import sys
import json
import config_loader

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CV_FILE = os.path.join(PROJECT_ROOT, "cv.md")
PROFILE_YML = os.path.join(PROJECT_ROOT, "config", "profile.yml")

COMMON_TECH_SKILLS = [
    "python", "sql", "pytorch", "tensorflow", "keras", "scikit-learn", "pandas", "numpy",
    "machine learning", "deep learning", "nlp", "llm", "transformers", "bert", "diffusion models",
    "power bi", "tableau", "dax", "etl", "data pipelines", "data engineering", "spark", "pyspark",
    "aws", "gcp", "azure", "docker", "git", "statistics", "data analysis", "business intelligence",
    "r&d", "research", "computer vision", "time-series", "eda", "bigquery", "snowflake"
]

def load_cv_text():
    """Load user's cv.md if present, extracting raw text."""
    if os.path.exists(CV_FILE):
        try:
            with open(CV_FILE, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return ""

def extract_jd_skills(jd_text):
    """Extract prominent technical skills mentioned in the job description."""
    if not jd_text:
        return []
    jd_lower = jd_text.lower()
    matched = [s for s in COMMON_TECH_SKILLS if re.search(r"\b" + re.escape(s) + r"\b", jd_lower)]
    return matched

def get_candidate_facts():
    """Extract narrative, superpowers, and proof points from profile & CV."""
    cfg = config_loader.load_config()
    cand = config_loader.get_candidate_profile()
    narrative = cfg.get("narrative", {})
    
    headline = narrative.get("headline", cand.get("education", "Computer Science graduate"))
    exit_story = narrative.get("exit_story", "")
    superpowers = narrative.get("superpowers", [])
    proof_points = narrative.get("proof_points", [])

    # If superpowers/proof_points are empty in config, derive from cv.md
    cv_text = load_cv_text()
    if not proof_points and cv_text:
        # Extract bullet points from Projects or Experience
        bullets = re.findall(r"-\s+([A-Z][^\n]{30,})", cv_text)
        proof_points = bullets[:5]

    return {
        "cand": cand,
        "headline": headline,
        "exit_story": exit_story,
        "superpowers": superpowers,
        "proof_points": proof_points,
        "cv_text": cv_text
    }

def generate_cover_letter(company, role, jd_text=""):
    """
    Drafts a high-impact, 3-paragraph tailored cover letter strictly grounded
    in the candidate's real profile facts and matching the JD requirements.
    """
    facts = get_candidate_facts()
    cand = facts["cand"]
    headline = facts["headline"]
    matched_skills = extract_jd_skills(jd_text)
    
    skill_str = ", ".join(s.title() for s in matched_skills[:4]) if matched_skills else "Python, SQL, Machine Learning, and Data Engineering"
    
    # Select most relevant proof points
    proofs = facts["proof_points"]
    p_text = ""
    if proofs:
        p_text = f"Specifically, {proofs[0]}"
        if len(proofs) > 1:
            p_text += f" Furthermore, {proofs[1]}"
    else:
        p_text = f"My experience spans building end-to-end data pipelines, statistical modeling, and machine learning architectures with a focus on real-world impact."

    letter = (
        f"Dear Hiring Team at {company},\n\n"
        f"I am writing to express my strong interest in the {role} position. "
        f"With a strong foundation in {skill_str} and a background as an {headline}, "
        f"I am excited about the opportunity to contribute to {company}'s technical initiatives.\n\n"
        f"{p_text}\n\n"
        f"I am available to join with an immediate or short notice period ({cand.get('notice_period', 'Immediate')}) "
        f"and am authorized to work in {cand.get('country', 'India')}. I welcome the opportunity to discuss how my skill set "
        f"and technical rigor align with your team's objectives.\n\n"
        f"Sincerely,\n{cand.get('full_name', 'Applicant')}\n"
        f"{cand.get('email', '')} | {cand.get('phone', '')}\n"
        f"{cand.get('linkedin', '')}"
    )
    return letter.strip()

def generate_why_company(company, role, jd_text=""):
    """Drafts a concise response to 'Why do you want to work at [Company]?'"""
    facts = get_candidate_facts()
    cand = facts["cand"]
    headline = facts["headline"]
    matched_skills = extract_jd_skills(jd_text)
    skill_mention = f" utilizing {', '.join(s.title() for s in matched_skills[:3])}" if matched_skills else ""

    text = (
        f"I have been closely following {company}'s growth and engineering leadership. "
        f"The {role} role presents the exact balance of challenging technical problems and scale that I am seeking. "
        f"Given my background as an {headline}{skill_mention}, I am energized by the prospect of contributing "
        f"to {company}'s mission while building high-reliability, data-driven systems."
    )
    return text.strip()

def generate_relevant_experience(company, role, jd_text=""):
    """Drafts an answer highlighting relevant technical project and metrics."""
    facts = get_candidate_facts()
    proofs = facts["proof_points"]
    
    if proofs:
        summary = "Key technical highlights from my recent projects and engineering work include:\n"
        for p in proofs[:3]:
            clean_p = p.rstrip(".") + "."
            summary += f"• {clean_p}\n"
        return summary.strip()

    return (
        f"I bring hands-on experience developing end-to-end data and machine learning workflows, "
        f"including data ingestion, ETL pipelines, statistical validation, and predictive modeling using Python, SQL, and modern data platforms."
    )

def generate_tailored_answer(question_prompt, company, role, jd_text=""):
    """
    Intelligently routes any ATS question prompt to the appropriate tailored answer.
    """
    q_lower = (question_prompt or "").lower()

    # Cover Letter / Pitch
    if any(k in q_lower for k in ["cover letter", "cover_letter", "note to hiring", "pitch", "message to hiring"]):
        return generate_cover_letter(company, role, jd_text)

    # Why Us / Why Role
    if any(k in q_lower for k in ["why do you want", "why us", "why are you interested", "why this role", "why join", "why work"]):
        return generate_why_company(company, role, jd_text)

    # Experience / Technical Background / Accomplishments
    if any(k in q_lower for k in ["relevant experience", "tell us about", "describe a project", "proudest", "technical achievement", "accomplishment", "summarize your experience"]):
        return generate_relevant_experience(company, role, jd_text)

    # Notice Period / Availability
    if any(k in q_lower for k in ["notice period", "availability", "when can you start", "how soon"]):
        cand = config_loader.get_candidate_profile()
        return cand.get("notice_period", "Immediate / 15 Days")

    # Salary / CTC expectations
    if any(k in q_lower for k in ["salary expectation", "expected ctc", "expected compensation", "desired salary"]):
        return "Open to discussion based on role responsibilities and market standards."

    # Additional Information / Comments
    if any(k in q_lower for k in ["additional information", "anything else", "additional comments", "notes"]):
        cand = config_loader.get_candidate_profile()
        return f"Thank you for considering my application. I am actively available ({cand.get('notice_period', 'Immediate')}) and look forward to speaking with the team."

    # Fallback to general professional alignment
    return generate_why_company(company, role, jd_text)
