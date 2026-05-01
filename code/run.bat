@echo off
REM Windows batch script to run the Forensic Triage Agent
REM Usage: run.bat [--dry-run|--sample|--input FILE|--output FILE]

setlocal enabledelayedexpansion

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Run the agent
python main.py %*

REM Deactivate on exit
deactivate
