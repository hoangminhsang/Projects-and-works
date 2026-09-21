Crescendo Attack Experiment
Overview

This repository contains the implementation and evaluation of the Crescendo multi-turn jailbreak attack on Large Language Models (LLMs), along with a defense mechanism using an LLM-based guard.

Project Structure
experiment/ folder

This folder includes two Jupyter notebooks:

cresendo_attack_main_code_current_version.ipynb
Implements the Crescendo attack without any defense mechanism.
cresendo_attack_with_llm_as_a_judge.ipynb
Implements the Crescendo attack with an LLM acting as a guard/judge, aiming to detect or mitigate malicious prompts.
Report
PART2_MAIN_version.pdf
Contains the full report of the experiment, including methodology, results, and analysis.
Experiment Recording
video3723818963.mp4
A recording of the experiment execution.

⚠️ Important:
To properly view the video:

Right-click the file
Select "Open with"
Choose Windows Media Player Legacy

Other media players may not display the video correctly.

Notes
The two notebooks are designed to be run independently.
Results may vary slightly across runs due to stochastic behavior in LLM responses.
Purpose

This project demonstrates:

The effectiveness of multi-turn jailbreak attacks (Crescendo)
The impact of adding a defensive layer using an LLM-based guard