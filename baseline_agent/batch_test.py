import requests
import time
import json
from datetime import datetime
import uuid
import csv

# Configuration
BASE_URL = "http://localhost:8000"  # Update if needed
APP_NAME = "baseline_agent"
USER_ID = "test1"

def load_questions_from_csv(csv_path):
    questions = []
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if row and row[0].strip():
                question = row[0].strip()
                if question.startswith('"') and question.endswith('"'):
                    question = question[1:-1]
                questions.append(question)
    return questions

# Load questions from prompts.csv (relative to this folder)
#QUESTIONS = load_questions_from_csv("data/prompts.csv")
QUESTIONS = load_questions_from_csv("data/stress_test_prompts.csv")

# Generate output file name with timestamp
now_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
OUTPUT_FILE = f"batch_test_results_{now_str}.json"


def create_session():
    url = f"{BASE_URL}/apps/{APP_NAME}/users/{USER_ID}/sessions"
    response = requests.post(url)
    response.raise_for_status()
    return response.json()["id"]


def send_question(session_id, question):
    url = f"{BASE_URL}/run"
    payload = {
        "app_name": APP_NAME,
        "user_id": USER_ID,
        "session_id": session_id,
        "new_message": {
            "role": "user",
            "parts": [{"text": question}]
        },
        "streaming": False
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def main():
    results = []
    # Create a session for all questions
    session_id = create_session()
    print(f"Created session: {session_id}")

    for question in QUESTIONS:
        agent_start = time.time()
        agent_start_iso = datetime.utcnow().isoformat() + "Z"
        try:
            response = send_question(session_id, question)
            print("RAW RESPONSE:", json.dumps(response, indent=2))
            agent_end = time.time()
            agent_end_iso = datetime.utcnow().isoformat() + "Z"
            elapsed = agent_end - agent_start

            answer = ""
            initial_answer = None
            original_message = None
            answer_flagged = None
            flagged_reasons = None
            # The response is a list of events, we need to find the one with the model's response
            for event in response:
                if event.get("content") and event["content"].get("parts"):
                    for part in event["content"]["parts"]:
                        if part.get("text"):
                            if initial_answer is None:
                                initial_answer = part["text"]
                            answer = part["text"]
                state = event.get("actions", {}).get("state_delta", {})
                if "original_user_message" in state and state["original_user_message"] is not None:
                    original_message = state["original_user_message"]
                if "answer_flagged" in state:
                    answer_flagged = state["answer_flagged"]
                if "flagged_reasons" in state:
                    flagged_reasons = state["flagged_reasons"]

            timing_info = {
                "agent_start": agent_start_iso,
                "agent_end": agent_end_iso,
                "elapsed": elapsed
            }
            state_info = {
                "original_message": original_message,
                "answer_flagged": answer_flagged,
                "flagged_reasons": flagged_reasons
            }
            results.append({
                "question": question,
                "initial_answer": initial_answer,
                "final_answer": answer,
                "state": state_info,
                "timing": timing_info
            })
            print(f"Q: {question}\nInitial A: {initial_answer}\nFinal A: {answer}\nElapsed: {elapsed:.2f}s\n---")
        except Exception as e:
            print(f"Error processing question '{question}': {e}")
            results.append({
                "question": question,
                "error": str(e)
            })

    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main() 