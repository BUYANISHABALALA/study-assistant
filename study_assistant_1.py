"""
AI Student Assistant - Step 1: Command-line Q&A over your notes.

What this does:
1. Loads your notes from a local text file (notes.txt)
2. Lets you type questions in the terminal
3. Sends your question + your notes to the Claude API
4. Prints the answer

Setup:
1. pip install anthropic
2. Get an API key from https://console.anthropic.com/
3. Set it as an environment variable:
   - Mac/Linux: export ANTHROPIC_API_KEY="your-key-here"
   - Windows (PowerShell): $env:ANTHROPIC_API_KEY="your-key-here"
4. Put your lecture notes in a file called notes.txt in the same folder
5. Run: python study_assistant.py
"""

import os
from anthropic import Anthropic

# --- Config ---
NOTES_FILE = "notes.txt"
MODEL = "claude-sonnet-4-6"


def load_notes(filepath: str) -> str:
    """Read notes from a text file. Returns empty string if file doesn't exist yet."""
    if not os.path.exists(filepath):
        print(f"[Note: {filepath} not found. Create it and paste your lecture notes inside.]")
        return ""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def ask_question(client: Anthropic, notes: str, question: str) -> str:
    """Send the question + notes as context to Claude and return the answer."""
    system_prompt = (
        "You are a helpful study assistant for a computer engineering student. "
        "Answer the student's question using the notes provided below as your main source. "
        "If the notes don't cover the question, say so, then answer from general knowledge. "
        "Keep answers clear and exam-relevant.\n\n"
        f"--- STUDENT'S NOTES ---\n{notes if notes else '(no notes loaded yet)'}\n--- END NOTES ---"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=system_prompt,
        messages=[{"role": "user", "content": question}],
    )

    # response.content is a list of blocks; grab the text block(s)
    return "".join(block.text for block in response.content if block.type == "text")


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        print("See the setup instructions at the top of this file.")
        return

    client = Anthropic(api_key=api_key)
    notes = load_notes(NOTES_FILE)

    print("=== AI Student Assistant ===")
    print("Type your question and press Enter. Type 'exit' to quit.\n")

    while True:
        question = input("You: ").strip()
        if question.lower() in ("exit", "quit"):
            print("Goodbye!")
            break
        if not question:
            continue

        answer = ask_question(client, notes, question)
        print(f"\nAssistant: {answer}\n")


if __name__ == "__main__":
    main()
