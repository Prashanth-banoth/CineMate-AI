
import json
import os
import uuid
from urllib.parse import urlencode
from urllib.request import urlopen

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from pydantic import BaseModel


# -------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is missing.")

client = genai.Client(api_key=GEMINI_API_KEY)

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


# Temporary in-memory storage.
# Data is cleared when the backend process restarts.

booking_sessions = {}
simulated_bookings = {}


# -------------------------------------------------------
# REQUEST MODELS
# -------------------------------------------------------

class BookingRequest(BaseModel):
    prompt: str
    session_id: str


class ConfirmBookingRequest(BaseModel):
    session_id: str
    seat_preference: str | None = None


# -------------------------------------------------------
# SIMULATED AGENT TOOLS
# -------------------------------------------------------

def search_showtimes(movie: str, theatre: str, date: str) -> dict:
    """
    Search simulated showtimes.
    This demo currently supports AMB Cinemas only.
    """

    if theatre.strip().lower() not in ["amb cinemas", "amb"]:
        return {
            "simulation": True,
            "available": False,
            "message": "This demo currently supports AMB Cinemas only."
        }

    return {
        "simulation": True,
        "available": True,
        "movie": movie,
        "theatre": "AMB Cinemas",
        "date": date,
        "showtimes": [
            {"show_id": "AMB-1830", "time": "6:30 PM"},
            {"show_id": "AMB-1900", "time": "7:00 PM"},
            {"show_id": "AMB-2130", "time": "9:30 PM"}
        ]
    }


def check_seat_availability(
    show_id: str,
    tickets: int,
    seat_preference: str
) -> dict:
    """
    Check sample seat availability.
    This does not reserve or hold real seats.
    """

    try:
        tickets = int(tickets)
    except (TypeError, ValueError):
        return {
            "simulation": True,
            "available": False,
            "message": "Ticket count must be a number."
        }

    if tickets < 1 or tickets > 6:
        return {
            "simulation": True,
            "available": False,
            "message": "Choose between 1 and 6 tickets."
        }

    seats_by_preference = {
        "front": ["F1", "F2", "F3", "F4"],
        "middle": ["M5", "M6", "M7", "M8"],
        "back": ["B1", "B2", "B3", "B4"]
    }

    preference = (seat_preference or "middle").strip().lower()

    if preference not in seats_by_preference:
        return {
            "simulation": True,
            "available": False,
            "message": "Choose front, middle or back seating."
        }

    available_seats = seats_by_preference[preference]

    if tickets > len(available_seats):
        return {
            "simulation": True,
            "available": False,
            "message": "Not enough seats available."
        }

    return {
        "simulation": True,
        "available": True,
        "show_id": show_id,
        "seat_preference": preference,
        "selected_seats": available_seats[:tickets],
        "ticket_count": tickets
    }


def create_simulated_booking(
    movie: str,
    theatre: str,
    date: str,
    time: str,
    tickets: int,
    seats: list[str],
    show_id: str
) -> dict:
    """
    Create a simulated booking after explicit confirmation.
    This does not book real cinema tickets.
    """

    if tickets < 1 or tickets > 6 or len(seats) != tickets:
        return {
            "success": False,
            "message": "Invalid ticket or seat details."
        }

    booking_id = f"CM-{uuid.uuid4().hex[:8].upper()}"

    booking = {
        "booking_id": booking_id,
        "movie": movie,
        "theatre": theatre,
        "date": date,
        "time": time,
        "tickets": tickets,
        "seats": seats,
        "show_id": show_id,
        "status": "CONFIRMED",
        "simulation": True
    }

    simulated_bookings[booking_id] = booking

    return {
        "success": True,
        "booking": booking,
        "message": "Simulated booking created successfully."
    }


# -------------------------------------------------------
# GEMINI AGENT RUNNER
# -------------------------------------------------------

def run_booking_agent(booking: dict) -> str:

    prompt = f"""
You are CineMate AI, an agentic movie booking assistant.

Booking details:
{json.dumps(booking)}

Your task is to prepare a simulated booking summary.

Follow these steps:

1. Call search_showtimes using the movie, theatre and date.
2. Inspect the returned showtimes.
3. Find the show whose time matches the user's requested time.
4. If no matching show exists, explain that the requested show is unavailable.
5. If a matching show exists, call check_seat_availability using its
   show_id, ticket count and seat preference.
6. Inspect the seat availability result.
7. If seats are available, present the booking summary and ask the user
   to confirm before a simulated booking record is created.
8. Never claim that real tickets were purchased, reserved or held.
9. Never invent showtimes or seat numbers.

Clearly state that showtimes and seats are simulated demo data.
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[
                search_showtimes,
                check_seat_availability
            ],
            automatic_function_calling=(
                types.AutomaticFunctionCallingConfig(
                    maximum_remote_calls=5
                )
            )
        )
    )

    return response.text or "Booking summary could not be generated."


# -------------------------------------------------------
# BASIC ROUTES
# -------------------------------------------------------

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


# -------------------------------------------------------
# OMDB MOVIE SEARCH
# -------------------------------------------------------

@app.get("/api/movies/search")
def search_movies(title: str):

    omdb_api_key = os.getenv("OMDB_API_KEY")

    if not omdb_api_key:
        raise HTTPException(
            status_code=500,
            detail="OMDb API key is missing."
        )

    params = urlencode({
        "s": title,
        "type": "movie",
        "apikey": omdb_api_key
    })

    url = f"https://www.omdbapi.com/?{params}"

    try:
        with urlopen(url, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        return data

    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"OMDb request failed: {str(error)}"
        )


# -------------------------------------------------------
# CREATE / UPDATE BOOKING CONVERSATION
# -------------------------------------------------------

@app.post("/api/booking")
def create_booking(request: BookingRequest):

    try:
        session_id = request.session_id.strip()

        if not session_id:
            raise HTTPException(
                status_code=400,
                detail="session_id is required."
            )

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

        # Do not modify an already-confirmed session.
        if previous_booking.get("confirmed_booking"):
            return {
                "status": "success",
                "booking": previous_booking,
                "message": (
                    "This session already has a confirmed "
                    "simulated booking."
                )
            }

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
2. Extract new information from the latest user message.
3. Never invent movie, theatre, date or showtime details.
4. Required fields: movie, date, time, theatre, tickets.
5. Seat preference is optional. If not provided, keep it null.
6. Ask only for details that are still missing.
7. Set ready_to_book true only when all required fields exist.
8. Do not claim that a real booking has been completed.
9. Return tickets as a number when provided.

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

        fields = [
            "movie",
            "date",
            "time",
            "theatre",
            "tickets",
            "seat_preference"
        ]

        # Preserve existing values when Gemini returns null.
        for field in fields:
            if booking_data.get(field) is None:
                booking_data[field] = previous_booking.get(field)

        # Ensure ticket count is an integer.
        if booking_data.get("tickets") is not None:
            try:
                booking_data["tickets"] = int(
                    booking_data["tickets"]
                )
            except (TypeError, ValueError):
                booking_data["tickets"] = None

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

        # Save booking details.
        booking_sessions[session_id] = {
            field: booking_data.get(field)
            for field in fields
        }

        if booking_data["ready_to_book"]:

            agent_response = run_booking_agent(booking_data)

            booking_data["agent_response"] = agent_response

            # Save complete booking details.
            booking_sessions[session_id] = booking_data

        return {
            "status": "success",
            "booking": booking_data,
            **(
                {"agent_response": booking_data["agent_response"]}
                if booking_data.get("agent_response")
                else {}
            )
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Gemini API error: {str(error)}"
        )


# -------------------------------------------------------
# CONFIRM SIMULATED BOOKING
# -------------------------------------------------------

def normalize_time(value: str) -> str:
    """Normalize values such as '7 PM' and '7:00 PM'."""

    return (
        value.strip()
        .upper()
        .replace(" ", "")
        .replace(":00", "")
    )


@app.post("/api/booking/confirm")
def confirm_booking(request: ConfirmBookingRequest):

    try:
        session_id = request.session_id.strip()

        if not session_id:
            raise HTTPException(
                status_code=400,
                detail="session_id is required."
            )

        booking = booking_sessions.get(session_id)

        if not booking:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Booking session not found. "
                    "Please prepare the booking first."
                )
            )

        # Prevent duplicate simulated bookings.
        if booking.get("confirmed_booking"):
            return {
                "status": "success",
                "message": "This simulated booking was already confirmed.",
                "simulation": True,
                "booking": booking["confirmed_booking"]
            }

        # Validate required fields.
        required_fields = [
            "movie",
            "theatre",
            "date",
            "time",
            "tickets"
        ]

        missing_fields = [
            field
            for field in required_fields
            if not booking.get(field)
        ]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Booking details are incomplete.",
                    "missing_details": missing_fields
                }
            )

        # Validate ticket count.
        try:
            tickets = int(booking["tickets"])

        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="Ticket count must be a valid number."
            )

        if tickets < 1 or tickets > 6:
            raise HTTPException(
                status_code=400,
                detail="Choose between 1 and 6 tickets."
            )

        # Get seat preference from frontend.
        selected_preference = (
            request.seat_preference
            or booking.get("seat_preference")
            or "middle"
        ).strip().lower()

        if selected_preference not in [
            "front",
            "middle",
            "back"
        ]:
            raise HTTPException(
                status_code=400,
                detail="Choose front, middle or back seating."
            )

        # Step 1: Search simulated showtimes.
        showtime_result = search_showtimes(
            movie=booking["movie"],
            theatre=booking["theatre"],
            date=booking["date"]
        )

        if not showtime_result.get("available"):
            raise HTTPException(
                status_code=400,
                detail=showtime_result.get(
                    "message",
                    "No showtimes available."
                )
            )

        # Step 2: Find the requested showtime.
        requested_time = normalize_time(
            str(booking["time"])
        )

        selected_show = next(
            (
                show
                for show in showtime_result["showtimes"]
                if normalize_time(show["time"]) == requested_time
            ),
            None
        )

        if not selected_show:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Requested showtime is unavailable in this demo."
                )
            )

        # Step 3: Check simulated seat availability.
        seat_result = check_seat_availability(
            show_id=selected_show["show_id"],
            tickets=tickets,
            seat_preference=selected_preference
        )

        if not seat_result.get("available"):
            raise HTTPException(
                status_code=400,
                detail=seat_result.get(
                    "message",
                    "Requested seats are unavailable."
                )
            )

        selected_seats = seat_result["selected_seats"]

        # Step 4: Create simulated booking.
        result = create_simulated_booking(
            movie=booking["movie"],
            theatre=booking["theatre"],
            date=booking["date"],
            time=selected_show["time"],
            tickets=tickets,
            seats=selected_seats,
            show_id=selected_show["show_id"]
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get(
                    "message",
                    "Simulated booking failed."
                )
            )

        # Save confirmed booking.
        booking["seat_preference"] = selected_preference
        booking["confirmed_booking"] = result["booking"]

        booking_sessions[session_id] = booking

        return {
            "status": "success",
            "message": "Simulated booking confirmed successfully.",
            "simulation": True,
            "booking": result["booking"]
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Booking confirmation error: {str(error)}"
        )


# -------------------------------------------------------
# LOOK UP A SIMULATED BOOKING
# -------------------------------------------------------

@app.get("/api/booking/{booking_id}")
def get_simulated_booking(booking_id: str):

    booking = simulated_bookings.get(booking_id)

    if not booking:
        raise HTTPException(
            status_code=404,
            detail="Simulated booking not found."
        )

    return {
        "status": "success",
        "simulation": True,
        "booking": booking
    }
