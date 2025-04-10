from fastapi import FastAPI, Query
import google.generativeai as genai
from playwright.sync_api import sync_playwright
import json
import time

# Set your Gemini API key
genai.configure(api_key="AIzaSyCpugWq859UTT5vaOe01EuONzFweYT2uUY")

app = FastAPI()

# Tidio live chat URL (Unassigned messages)
TIDIO_CHAT_URL = "https://www.tidio.com/panel/inbox/conversations/unassigned/"

# Function to scrape the website and extract content
def scrape_website(url="https://tripzoori-gittest1.fly.dev/"):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)

        # Wait for the page to load completely
        page.wait_for_selector("body")

        # Extract all visible text from the page
        page_content = page.inner_text("body")

        # Store scraped data in a JSON file
        with open("website_data.json", "w", encoding="utf-8") as f:
            json.dump({"content": page_content}, f, indent=4)

        browser.close()
        return page_content

# Function to load scraped data
def load_data():
    try:
        with open("website_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("content", "")
    except FileNotFoundError:
        return scrape_website()

# Function to send a message to the Tidio live chat
def send_message_to_tidio(message: str):
    """Automates sending a message to Tidio live chat."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(TIDIO_CHAT_URL)

        # Wait for Tidio's chat interface to load
        page.wait_for_selector("textarea", timeout=10000)

        # Type the message
        page.fill("textarea", message)
        time.sleep(2)

        # Press Enter to send the message
        page.keyboard.press("Enter")
        time.sleep(2)

        browser.close()

# Function to check if the bot should transfer to a human agent
def needs_human_agent(question: str, answer: str) -> bool:
    """Checks if the bot's answer is insufficient and requires human intervention."""
    low_confidence_phrases = [
        "I can't", "I do not", "I am unable", "I don't have information",
        "I cannot", "I am just an AI", "I don't know", "I only provide information",
        "I'm not sure", "I apologize", "Unfortunately, I cannot" 
    ]

    trigger_keywords = ["complaints", "refunds", "booking issue", "flight problem", "support", "human agent", "live agent"]

    # If the answer is vague or the user explicitly asks for help, escalate
    return any(phrase in answer.lower() for phrase in low_confidence_phrases) or any(keyword in question.lower() for keyword in trigger_keywords)

# Function to ask questions using Gemini AI
def ask_question(question: str):
    data = load_data()

    prompt = f"""
    You are an AI assistant that answers questions based on the website content.
    If you are unsure or cannot answer accurately, indicate uncertainty.
    Website Data: {data}
    Question: {question}
    Answer:
    """

    model = genai.GenerativeModel("gemini-1.5-pro")
    response = model.generate_content(prompt)
    answer = response.text.strip()

    # If the bot cannot provide a valid answer, send the message to Tidio
    if needs_human_agent(question, answer):
        send_message_to_tidio(f"User asked: '{question}'\nBot could not answer.")
        return {
            "answer": "I am unable to answer this question. A human agent has been notified.",
            "status": "transferred_to_human"
        }

    return {"question": question, "answer": answer}

@app.get("/ask")
def get_answer(question: str = Query(..., title="Question", description="Ask a question about the website")):
    # If the user explicitly requests a human agent
    if any(keyword in question.lower() for keyword in ["transfer to human agent", "talk to a person", "speak to support"]):
        send_message_to_tidio(f"User requested a human agent for: '{question}'")
        return {
            "answer": "A human agent has been notified and will respond shortly.",
            "status": "transferred_to_human"
        }

    return ask_question(question)
