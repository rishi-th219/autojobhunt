# Article Digest — Proof Points

Detailed proof points behind the CV bullets for the CHiPS / Dept. of Health & Family Welfare (Govt. of Chhattisgarh) internship. Source: user-provided internship writeup, 2026-09-01.

## Context

Posted under the Secretary of the Department of Health & Family Welfare, Govt. of Chhattisgarh, as a Data Analyst intern. The department has 5 sub-departments: DHS, DME, CGMSCL, Ayush, CFD. Work was incremental across three linked tasks, each building on data from the previous one.

## Proof Point 1 — Statewide Attendance Dashboard (DHS / AEBAS)

- **What:** Built a 6-page Power BI dashboard (2 overview pages + 4 drill-down pages structured district → facility → designation → employee) to analyze and monitor employee attendance statewide, across all 33 districts of Chhattisgarh.
- **Data source:** AEBAS (Aadhaar-Enabled Biometric Attendance System), backed by MariaDB.
- **KPIs defined:** average working hours, employees present at least once, missed-out times, and related attendance metrics.
- **Challenges solved:**
  - Inconsistent employee names and duplicate designations in the raw data.
  - Three distinct employee categories requiring different handling: regular, contractual, and National Health Mission (NHM) staff.
- **Hero framing:** Went from raw, inconsistent biometric attendance data to a single statewide reporting layer covering every facility and every employee category in the state health system.

## Proof Point 2 — Bonded Doctor Compliance Tracing (DHS + Treasury)

- **What:** Narrowed focus to a specific, high-stakes subset of the workforce: "bonded doctors" — students from government medical colleges who owe mandatory service (2 years for UG, 3 years for PG graduates) at Chhattisgarh government health facilities (PHCs, CHCs, SHCs, CHs, DH, and medical colleges) across the 33 districts.
- **The problem:** A meaningful share of bonded doctors did not join their assigned posting — or were paid without actually reporting to the appointed facility.
- **Action:** Pulled and linked data from the Chhattisgarh State Treasury with the AEBAS attendance data from Proof Point 1, mapping AEBAS attendance IDs to Treasury employee codes to build a single identity-resolved view per doctor.
- **Result:** Classified every bonded doctor into one of three defaulter categories:
  1. Never joined at all.
  2. Joined formally but never registered/reported at the appointed facility.
  3. Joined the appointed facility but has no or improper attendance logging.
- **Hero framing:** Closed a monitoring gap the department had flagged — turned an untraceable compliance obligation into a queryable, categorized compliance dataset.

## Proof Point 3 — End-to-End Doctor Performance Dashboard (DHS + Treasury + e-Hospital)

- **What:** Extended the attendance (Proof Point 1) + incentive/Treasury (Proof Point 2) data into a full doctor performance dashboard by adding OPD (out-patient department) data pulled from the Government of India's next-gen e-Hospital platform.
- **The hardest part:** e-Hospital is built as a modular system maintained by NIC (National Informatics Centre), where each module has its own independently developed backend but shares a common frontend framework — so there was no single script or clean join path to link the data; reconciling the modules required direct coordination with NIC's data-engineering teams.
- **Result:** A single reporting layer joining attendance + treasury incentive data + OPD activity per doctor — the most technically difficult of the three tasks, and the one requiring the most cross-team (NIC) coordination.

## Technical thread across all three

- **Task 1 → Task 2:** Attendance ID (`emp_id` from AEBAS) mapped to `emp_code` from the Treasury system.
- **Task 2 → Task 3:** Combined attendance + treasury data linked to next-gen e-Hospital OPD data — no automatable join available; required manual reconciliation across independently built NIC backend modules.
- **Underlying skill demonstrated:** multi-source ETL and identity resolution across systems that were never designed to talk to each other, escalating in both data-linkage difficulty and organizational stakes (routine attendance → compliance/accountability → full performance management) across the three tasks.

## CGMSCL Supply-Chain Analytics (separate sub-department engagement)

- Analyzed drug supply data (EDL/Non-EDL — Essential vs. Non-Essential Drug List) for CGMSCL via OracleDB.
- Performed ABC, VED, and SDE inventory analysis and published dashboards on Oracle Analytics Cloud to support supply-chain decisions.

## Proof Point 4 — Proactive 5G Handover Prediction (M.Tech Thesis)

Source: user-provided project writeup, 2026-09-01.

- **Problem:** In 5G mmWave networks, physical obstacles cause instant signal drops (20–30 dB within milliseconds). Standard network protocols are reactive — they wait for the signal to degrade and enforce a mandatory countdown timer (Time-To-Trigger) before switching cell towers, causing frequent Radio Link Failures (RLFs) and dropped connections.
- **What was built:** A proactive AI decision engine replacing that reactive protocol, combining three layers:
  1. **Context Encoder (GRU):** encodes historical 3D drive-test telemetry (RSRP, RSRQ, CINR, GPS, distance, azimuth, elevation) into a compact latent summary vector, filtering short-term radio noise.
  2. **Denoising Network (DDPM, accelerated with DDIM):** conditioned on the GRU summary vector, generates 50 distinct future signal trajectories for uncertainty quantification over the look-forward horizon; DDIM sampling makes it fast enough for real-time edge deployment (O-RAN Near-RT RIC / xApp).
  3. **Two-Stage Policy Engine (Random Forest):** scans the 50 generated paths against physical coverage thresholds (e.g. -85 dBm / -100 dBm), computes a probability of failure, and issues a tri-state decision — stay connected, prepare handover, or trigger immediate handover (P(fail) > 80%).
- **Key technical innovations:**
  - **Custom dual-masking loss function:** cell masking (ignores distant/weak towers to focus compute on viable targets) + time-point masking (hyper-focuses accuracy on the exact split-second timestamps where handover decisions occur).
  - **SMOTE + Tomek Links pipeline:** real-world driving data is heavily imbalanced (~98% safe driving vs ~2% signal drops); SMOTE generates synthetic signal-crash trajectories to remove majority-class bias, Tomek Links cleans noisy points along the decision boundary.
  - **Explainable two-stage design:** decouples the regression (forecasted physical dBm curves) from the classification (Random Forest policy), giving network engineers physical explainability instead of a black box.
- **Result:** 97.64% F1-score on failure classification.
- **Business framing (useful for non-technical audiences):** eliminates a reactive, timer-based bottleneck; protects SLAs for high-reliability applications (URLLC) by reducing Radio Link Failures; reduces unnecessary network signaling overhead (fewer ping-pong handovers); the explainable two-stage design is what builds enterprise trust/adoption, not just the raw accuracy number.

## Proof Point 5 — AI vs. Human Text Classification Pipeline

Source: user-provided project writeup, 2026-09-01.

- **Objective:** End-to-end NLP system to detect synthetic, LLM-generated text (e.g. GPT-3/ChatGPT) vs. human-written text, built and compared across two distinct architectural approaches.
- **Data pipeline:** stratified 80/20 train/test split (preserving exact class ratios); text normalized via NFKD (`tf_text.normalize_utf8`) plus regex noise removal; tokenized into a 20,000-word vocabulary, sequences padded to length 128.
- **Pipeline 1 — ML baseline (BERT + XGBoost):** extracted dense 768-dim contextual embeddings from pre-trained BERT's `[CLS]` token, classified with XGBoost for lightweight, low-latency inference.
- **Pipeline 2 — deep learning hybrid architecture:** trainable embedding layer (128-dim) → Bidirectional LSTM (forward/backward sequence flow to catch unnatural sentence structure) → Transformer block (multi-head self-attention + layer norm for long-range document context) → 1D CNN, kernel size 5 (acts as an automated n-gram extractor for repetitive/robotic phrasing) → global max-pooling + sigmoid output.
- **Training controls:** dropout (0.5) against node co-adaptation; early stopping (patience=4) with best-weight restoration; `ReduceLROnPlateau` to dynamically halve the learning rate when validation loss stalled.
- **Result:** 99% precision (minimizing false accusations of AI-generated text) / 98% recall (~99% overall F1/accuracy) on held-out data.
