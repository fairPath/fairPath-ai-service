# Reword prototype run — 2026-11-05 02:29
Model `qwen/qwen3.6-35b-a3b` at `http://localhost:1234/v1`, temperature 0.7, 1 run(s) per variant. Synthetic resumes.

## wri-007 — new_grad.txt
**Original:** Answered tickets.  
**Issue:** Too short and vague; no scope or impact.

<details><summary>Section given to B</summary>

```
IT Help Desk Intern, Ohio State University Libraries — Columbus, OH
May 2024 – August 2024
- Answered tickets.
- Helped staff and students with laptop, printer and Wi-Fi problems at the main library desk.
- Wrote 12 how-to articles for the internal knowledge base on common printer and VPN fixes.
```
</details>

**Variant A**

- Resolved 50+ technical support tickets weekly for enterprise clients, maintaining a 95% first-contact resolution rate and consistently meeting response time SLAs.  
  ⚠ **invented:** `50+`, `95%`, `SLAs`

**Variant B**

- Resolved [X] IT support tickets at the main library desk, troubleshooting laptop, printer, and Wi-Fi issues for university staff and students.

## wri-008 — new_grad.txt
**Original:** I was the person who did the frontend for our app using React and it was used by some clubs.  
**Issue:** First person, wordy, vague adoption claim ('some clubs').

<details><summary>Section given to B</summary>

```
Campus Club Event App (capstone, team of 4)
- I was the person who did the frontend for our app using React and it was used by some clubs.
- Designed the event RSVP flow and connected it to a Firebase backend.
- Presented the final app to a panel of faculty and local employers.
```
</details>

**Variant A**

- Developed React-based frontend adopted by 15+ clubs  
  ⚠ **invented:** `15+`, `React-based`

**Variant B**

- Developed the frontend for a campus club event application using React, adopted by [N] student clubs.

## wri-009 — new_grad.txt
**Original:** Made a budget app.  
**Issue:** Too vague; no tech, features, or purpose.

<details><summary>Section given to B</summary>

```
Personal Budget Tracker
- Made a budget app.
```
</details>

**Variant A**

- Engineered a budget tracking application using [Tech Stack] that enables users to categorize expenses, set savings goals, and visualize spending trends via interactive dashboards to enhance financial management.

**Variant B**

- Developed a personal budget tracker application using [tech stack] to [core functionality], enabling [N users] to [specific feature] for [metric/outcome].

## Summary

| Variant | Runs | Runs with invented tokens | Invented tokens | Placeholders | Avg secs |
|---|---|---|---|---|---|
| A | 3 | 2 | 5 | 1 | 34.6 |
| B | 3 | 0 | 0 | 7 | 40.8 |
