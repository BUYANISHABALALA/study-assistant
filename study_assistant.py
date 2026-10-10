"""
AI Student Assistant - v2

What's new compared with v1:
1. Conversation memory: follow-up questions like "explain that more simply" work.
2. Error handling: API problems print one clear line instead of a crash.
3. Plain-text answers: no markdown symbols in the terminal.
4. notes.txt is found next to this script, wherever you run it from.

Setup:
- pip install anthropic python-dotenv
- Put ANTHROPIC_API_KEY=your-key in a .env file next to this script
  (or set it in the terminal with $env:ANTHROPIC_API_KEY="your-key").
- Put your lecture notes in notes.txt next to this script.
- Run: python study_assistant_v2.py

Commands while running:
- clear : forget the conversation and start fresh (notes stay loaded)
- exit  : quit
"""

import os
from pathlib import Path

import anthropic
from anthropic import Anthropic

# python-dotenv is optional: if it isn't installed, the script still works
# as long as the key is set in the terminal.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- Config ---
BASE_DIR = Path(__file__).parent
NOTES_FILE = BASE_DIR / "notes.txt"
MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 1000
MAX_HISTORY_MESSAGES = 20  # last 10 question/answer pairs; keeps costs down


def load_notes(filepath: Path) -> str:
    """Read notes from a text file. Returns empty string if it doesn't exist."""
    if not filepath.exists():
        print(f"[Note: {filepath.name} not found. Create it next to this script "
              "and paste your lecture notes inside.]")
        return ""
    return filepath.read_text(encoding="utf-8")


def build_system_prompt(notes: str) -> str:
    return (
        "You are a helpful study assistant for a computer engineering student. "
        "Answer the student's question using the notes provided below as your main source. "
        "If the notes don't cover the question, say so, then answer from general knowledge. "
        "Keep answers clear and exam-relevant. "
        "Respond in plain text only: no markdown, no headings, no bold, no tables. "
        "Use short paragraphs and simple dashes for lists.\n\n"
        f"--- STUDENT'S NOTES ---\n{notes if notes else '(no notes loaded yet)'}\n--- END NOTES ---"
    )


def ask_question(client: Anthropic, system_prompt: str, history: list) -> str:
    """Send the whole conversation so far to the API and return the answer text."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=history,
    )
    return "".join(block.text for block in response.content if block.type == "text")


def explain_error(err: Exception) -> str:
    """Turn an API exception into one short, readable line."""
    if isinstance(err, anthropic.AuthenticationError):
        return "Your API key was rejected. Check ANTHROPIC_API_KEY (or your .env file)."
    if isinstance(err, anthropic.PermissionDeniedError):
        return "Your API key doesn't have permission to do this."
    if isinstance(err, anthropic.NotFoundError):
        return f"Model '{MODEL}' was not found. Check the MODEL name at the top of the script."
    if isinstance(err, anthropic.RateLimitError):
        return "Too many requests right now. Wait a few seconds and try again."
    if isinstance(err, anthropic.APIConnectionError):
        return "Couldn't reach the API. Check your internet connection and try again."
    if isinstance(err, anthropic.BadRequestError):
        if "credit balance" in str(err).lower():
            return "Your credit balance is too low. Add credit under Plans & Billing in the console."
        return f"The request was rejected: {err}"
    if isinstance(err, anthropic.APIStatusError):
        return f"The API returned an error (status {err.status_code}). Try again in a moment."
    return f"Unexpected error: {err}"


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY is not set.")
        print("Add it to a .env file next to this script, or set it in the terminal.")
        return

    client = Anthropic(api_key=api_key)
    notes = load_notes(NOTES_FILE)
    system_prompt = build_system_prompt(notes)
    history = []  # list of {"role": "user"/"assistant", "content": "..."}

    print("=== AI Student Assistant (v2) ===")
    print("Type your question and press Enter.")
    print("Commands: 'clear' starts a fresh conversation, 'exit' quits.\n")

    while True:
        try:
            question = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if question.lower() in ("exit", "quit"):
            print("Goodbye!")
            break
        if question.lower() == "clear":
            history = []
            print("[Conversation cleared. Notes are still loaded.]\n")
            continue
        if not question:
            continue

        history.append({"role": "user", "content": question})

        try:
            answer = ask_question(client, system_prompt, history)
        except Exception as err:
            # Remove the question that failed so the history stays valid.
            history.pop()
            print(f"\n[Error] {explain_error(err)}\n")
            continue

        history.append({"role": "assistant", "content": answer})
        # Keep only the most recent messages (always an even number, so the
        # list still starts with a user message).
        if len(history) > MAX_HISTORY_MESSAGES:
            history = history[-MAX_HISTORY_MESSAGES:]

        print(f"\nAssistant: {answer}\n")


if __name__ == "__main__":
    main()
