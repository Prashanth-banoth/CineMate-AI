
import os
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY is missing.")

client = genai.Client(api_key=api_key)

app = FastAPI(
    title="CineMate AI API",
    description="AI-powered movie booking assistant",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:3000",
    "https://frontend-vert-xi-60.vercel.app",
],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Temporary in-memory conversation storage
booking_sessions = {}


class BookingRequest(BaseModel):
    prompt: str
    session_id: str


@app.get("/")
def home():
    return {
        "message": "Welcome to CineMate AI Backend!",
        "status": "Running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "project": "CineMate AI"
    }


@app.post("/api/booking")
def create_booking(request: BookingRequest):
    try:
        session_id = request.session_id

        previous_booking = booking_sessions.get(
            session_id,
            {
                "movie": None,
                "date": None,
                "time": None,
                "theatre": None,
                "tickets": None,
                "seat_preference": None
            }
        )

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=f"""
You are CineMate AI, a movie booking assistant.

Previous booking details:
{json.dumps(previous_booking)}

New user message:
{request.prompt}

Update the existing booking using the new user message.

IMPORTANT RULES:
1. Preserve previous details unless the user changes them.
2. Extract new information from the latest message.
3. Never invent movie, theatre, date or showtime details.
4. Required fields: movie, date, time, theatre, tickets.
5. Seat preference is optional.
6. Ask only for details that are still missing.
7. Set ready_to_book true only when all required fields exist.
8. Do not claim a real booking has been completed.

Return ONLY valid JSON in this format:

{{
  "movie": null,
  "date": null,
  "time": null,
  "theatre": null,
  "tickets": null,
  "seat_preference": null,
  "missing_details": [],
  "ready_to_book": false,
  "reply": "Friendly response to the user"
}}
""",
            config={
                "response_mime_type": "application/json"
            }
        )

        booking_data = json.loads(response.text)

        # Preserve existing details if Gemini returns null
        fields = [
            "movie",
            "date",
            "time",
            "theatre",
            "tickets",
            "seat_preference"
        ]

        for field in fields:
            if booking_data.get(field) is None:
                booking_data[field] = previous_booking.get(field)

        # Calculate missing required details
        required_fields = [
            "movie",
            "date",
            "time",
            "theatre",
            "tickets"
        ]

        booking_data["missing_details"] = [
            field
            for field in required_fields
            if not booking_data.get(field)
        ]

        booking_data["ready_to_book"] = (
            len(booking_data["missing_details"]) == 0
        )

        # Save updated booking in memory
        booking_sessions[session_id] = {
            field: booking_data.get(field)
            for field in fields
        }

        return {
            "status": "success",
            "booking": booking_data
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Gemini API error: {str(error)}"
        )
