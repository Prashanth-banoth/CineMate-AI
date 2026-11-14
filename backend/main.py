
import json
import os
import uuid
import hashlib

import psycopg
from psycopg.rows import dict_row
from psycopg.errors import UniqueViolation

from urllib.parse import urlencode
from urllib.request import urlopen

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from pydantic import BaseModel, Field


# -------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is missing.")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is missing.")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://",
        "postgresql://",
        1
    )

client = genai.Client(api_key=GEMINI_API_KEY)

app = FastAPI(
    title="CineMate AI API",
    description="AI-powered movie discovery and booking assistant",
    version="5.0.0"
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


# -------------------------------------------------------
# STORAGE
# -------------------------------------------------------

booking_sessions = {}


def get_db():
    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
        connect_timeout=15
    )


def initialize_database():

    with get_db() as connection:

        connection.execute("""
            CREATE TABLE IF NOT EXISTS booked_seats (
                id BIGSERIAL PRIMARY KEY,
                show_key TEXT NOT NULL,
                seat_number TEXT NOT NULL,
                booking_id TEXT NOT NULL,
                UNIQUE(show_key, seat_number)
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS simulated_bookings (
                booking_id TEXT PRIMARY KEY,
                booking_data JSONB NOT NULL
            )
        """)


initialize_database()


# -------------------------------------------------------
# REQUEST MODELS
# -------------------------------------------------------

class BookingRequest(BaseModel):
    prompt: str
    session_id: str


class ConfirmBookingRequest(BaseModel):
    session_id: str
    seat_preference: str | None = None
    selected_seats: list[str] | None = None


class MovieRecommendationRequest(BaseModel):
    mood: str = Field(min_length=1, max_length=50)
    language: str = "Any"
    genre: str = "Any"


# -------------------------------------------------------
# THEATRE CONFIGURATION
# -------------------------------------------------------

DEMO_THEATRES = [
    {
        "name": "AMB Cinemas",
        "available": True
    }
]


# -------------------------------------------------------
# SEAT CONFIGURATION
# -------------------------------------------------------

SEATS_BY_PREFERENCE = {
    "front": [f"F{i}" for i in range(1, 31)],
    "middle": [f"M{i}" for i in range(1, 41)],
    "back": [f"B{i}" for i in range(1, 31)]
}


# -------------------------------------------------------
# TIME NORMALIZATION
# -------------------------------------------------------

def normalize_time(value: str) -> str:

    return (
        value.strip()
        .upper()
        .replace(" ", "")
        .replace(":00", "")
    )


# -------------------------------------------------------
# SHOW KEY GENERATION
# -------------------------------------------------------

def make_show_key(
    movie: str,
    theatre: str,
    date: str,
    time: str
) -> str:

    raw_value = "|".join([
        movie.strip().lower(),
        theatre.strip().lower(),
        date.strip().lower(),
        time.strip().lower()
    ])

    return hashlib.sha256(
        raw_value.encode("utf-8")
    ).hexdigest()


# -------------------------------------------------------
# GET BOOKED SEATS
# -------------------------------------------------------

def get_booked_seats(show_key: str) -> list[str]:

    with get_db() as connection:

        rows = connection.execute(
            """
            SELECT seat_number
            FROM booked_seats
            WHERE show_key = %s
            """,
            (show_key,)
        ).fetchall()

    return [
        row["seat_number"]
        for row in rows
    ]


# -------------------------------------------------------
# SHOWTIME SEARCH AND THEATRE AVAILABILITY
# -------------------------------------------------------

def search_showtimes(
    movie: str,
    theatre: str,
    date: str
) -> dict:

    selected_theatre = theatre.strip().lower()

    supported_theatre = next(
        (
            item
            for item in DEMO_THEATRES
            if (
                item["name"].lower() == selected_theatre
                or (
                    item["name"] == "AMB Cinemas"
                    and selected_theatre == "amb"
                )
            )
        ),
        None
    )

    if not supported_theatre:

        available_theatres = [
            item["name"]
            for item in DEMO_THEATRES
            if item["available"]
        ]

        return {
            "simulation": True,
            "available": False,
            "requested_theatre": theatre,
            "available_theatres": available_theatres,
            "message": (
                f"{theatre} is unavailable in this demo. "
                f"Available theatres: "
                f"{', '.join(available_theatres)}."
            )
        }

    sample_times = [
        "6:30 PM",
        "7:00 PM",
        "9:30 PM"
    ]

    showtimes = []

    for show_time in sample_times:

        show_key = make_show_key(
            movie,
            supported_theatre["name"],
            date,
            show_time
        )

        showtimes.append({
            "show_id": show_key,
            "time": show_time
        })

    return {
        "simulation": True,
        "available": True,
        "movie": movie,
        "theatre": supported_theatre["name"],
        "date": date,
        "showtimes": showtimes,
        "available_theatres": [
            item["name"]
            for item in DEMO_THEATRES
            if item["available"]
        ]
    }


# -------------------------------------------------------
# DYNAMIC SEAT AVAILABILITY
# -------------------------------------------------------

def check_seat_availability(
    show_id: str,
    tickets: int,
    seat_preference: str
) -> dict:

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

    preference = (
        seat_preference or "middle"
    ).strip().lower()

    if preference not in SEATS_BY_PREFERENCE:

        return {
            "simulation": True,
            "available": False,
            "message": "Choose front, middle or back seating."
        }

    all_seats = SEATS_BY_PREFERENCE[preference]

    booked_seats = set(
        get_booked_seats(show_id)
    )

    available_seats = [
        seat
        for seat in all_seats
        if seat not in booked_seats
    ]

    if len(available_seats) < tickets:

        return {
            "simulation": True,
            "available": False,
            "message": (
                f"Only {len(available_seats)} seats are available "
                f"in the {preference} section."
            ),
            "available_count": len(available_seats)
        }

    return {
        "simulation": True,
        "available": True,
        "show_id": show_id,
        "seat_preference": preference,
        "selected_seats": available_seats[:tickets],
        "ticket_count": tickets,
        "available_count": len(available_seats),
        "booked_seats": sorted(booked_seats)
    }


# -------------------------------------------------------
# CREATE SIMULATED BOOKING
# -------------------------------------------------------

def create_simulated_booking(
    movie: str,
    theatre: str,
    date: str,
    time: str,
    tickets: int,
    seats: list[str],
    show_id: str
) -> dict:

    if (
        tickets < 1
        or tickets > 6
        or len(seats) != tickets
        or len(set(seats)) != len(seats)
    ):
        return {
            "success": False,
            "message": "Invalid ticket or seat details."
        }

    booking_id = (
        f"CM-{uuid.uuid4().hex[:8].upper()}"
    )

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

    try:

        with get_db() as connection:

            for seat in seats:

                connection.execute(
                    """
                    INSERT INTO booked_seats (
                        show_key,
                        seat_number,
                        booking_id
                    )
                    VALUES (%s, %s, %s)
                    """,
                    (
                        show_id,
                        seat,
                        booking_id
                    )
                )

            connection.execute(
                """
                INSERT INTO simulated_bookings (
                    booking_id,
                    booking_data
                )
                VALUES (%s, %s::jsonb)
                """,
                (
                    booking_id,
                    json.dumps(booking)
                )
            )

        return {
            "success": True,
            "booking": booking,
            "message": "Simulated booking created successfully."
        }

    except UniqueViolation:

        return {
            "success": False,
            "message": (
                "One or more selected seats were just booked. "
                "Please check availability again."
            )
        }

    except Exception as error:

        print("Database booking error:", str(error))

        return {
            "success": False,
            "message": "Database booking failed."
        }


# -------------------------------------------------------
# GEMINI BOOKING AGENT
# -------------------------------------------------------

def run_booking_agent(booking: dict) -> str:

    prompt = f"""
You are CineMate AI, an agentic movie booking assistant.

Booking details:
{json.dumps(booking)}

Your task is to prepare a simulated booking summary.

Follow these steps:

1. Inspect the booking details.
2. Confirm the selected theatre and showtime.
3. Never invent showtimes or seat numbers.
4. Never claim that real tickets were purchased, reserved or held.
5. Clearly state that showtimes and seats are simulated demo data.
6. Ask the user to select seats before final confirmation.
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt
    )

    return (
        response.text
        or "Booking summary could not be generated."
    )


# -------------------------------------------------------
# OMDB MOVIE DETAILS
# -------------------------------------------------------

def get_verified_movie_details(title: str) -> dict | None:

    if not OMDB_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="OMDb API key is missing."
        )

    params = urlencode({
        "t": title,
        "type": "movie",
        "plot": "short",
        "apikey": OMDB_API_KEY
    })

    url = f"https://www.omdbapi.com/?{params}"

    try:

        with urlopen(url, timeout=15) as response:

            data = json.loads(
                response.read().decode("utf-8")
            )

        if data.get("Response") != "True":
            return None

        return {
            "Title": data.get("Title"),
            "Year": data.get("Year"),
            "imdbID": data.get("imdbID"),
            "Type": data.get("Type"),
            "Poster": data.get("Poster"),
            "Genre": data.get("Genre"),
            "Plot": data.get("Plot"),
            "imdbRating": data.get("imdbRating"),
            "Language": data.get("Language"),
            "Runtime": data.get("Runtime")
        }

    except HTTPException:
        raise

    except Exception as error:

        print("OMDb recommendation lookup error:", str(error))

        return None


# -------------------------------------------------------
# AI MOVIE RECOMMENDATIONS
# -------------------------------------------------------

def generate_movie_recommendations(
    mood: str,
    language: str,
    genre: str
) -> list[dict]:

    prompt = f"""
You are CineMate AI, a movie recommendation expert.

Recommend 8 real and released movies based on:

Mood: {mood}
Language: {language}
Genre: {genre}

Rules:
1. Recommend real released movies only.
2. Match the preferences as closely as possible.
3. Do not invent movie titles.
4. Return movie titles only.
5. Avoid duplicates.
6. Respect the language preference.

Return ONLY JSON:

{{
    "movies": [
        "Movie Title 1",
        "Movie Title 2"
    ]
}}
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )

    result = json.loads(
        response.text or "{}"
    )

    titles = result.get("movies", [])

    if not isinstance(titles, list):
        return []

    verified_movies = []
    seen_ids = set()

    for title in titles[:8]:

        if not isinstance(title, str) or not title.strip():
            continue

        movie = get_verified_movie_details(title.strip())

        if not movie:
            continue

        imdb_id = movie.get("imdbID")

        if not imdb_id or imdb_id in seen_ids:
            continue

        seen_ids.add(imdb_id)
        verified_movies.append(movie)

    return verified_movies


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
# DATABASE HEALTH CHECK
# -------------------------------------------------------

@app.get("/health/database")
def database_health_check():

    try:

        with get_db() as connection:

            row = connection.execute(
                "SELECT current_database() AS database"
            ).fetchone()

        return {
            "status": "connected",
            "database": row["database"],
            "provider": "PostgreSQL",
            "simulation": True
        }

    except Exception as error:

        print("Database health check error:", str(error))

        raise HTTPException(
            status_code=503,
            detail="PostgreSQL database connection failed."
        )


# -------------------------------------------------------
# OMDB MOVIE SEARCH
# -------------------------------------------------------

@app.get("/api/movies/search")
def search_movies(title: str):

    if not OMDB_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="OMDb API key is missing."
        )

    params = urlencode({
        "s": title,
        "type": "movie",
        "apikey": OMDB_API_KEY
    })

    url = f"https://www.omdbapi.com/?{params}"

    try:

        with urlopen(url, timeout=15) as response:

            data = json.loads(
                response.read().decode("utf-8")
            )

        return data

    except Exception as error:

        raise HTTPException(
            status_code=502,
            detail=f"OMDb request failed: {str(error)}"
        )


# -------------------------------------------------------
# AI MOVIE RECOMMENDATION API
# -------------------------------------------------------

@app.post("/api/movies/recommend")
def recommend_movies(request: MovieRecommendationRequest):

    mood = request.mood.strip()
    language = request.language.strip() or "Any"
    genre = request.genre.strip() or "Any"

    if not mood:
        raise HTTPException(
            status_code=400,
            detail="Please select a mood."
        )

    try:

        movies = generate_movie_recommendations(
            mood=mood,
            language=language,
            genre=genre
        )

        return {
            "status": "success",
            "preferences": {
                "mood": mood,
                "language": language,
                "genre": genre
            },
            "count": len(movies),
            "movies": movies,
            "message": (
                "AI recommendations generated and movie details "
                "verified using OMDb."
            )
        }

    except HTTPException:
        raise

    except Exception as error:

        print("Movie recommendation error:", str(error))

        raise HTTPException(
            status_code=500,
            detail="Unable to generate movie recommendations."
        )


# -------------------------------------------------------
# CREATE / UPDATE BOOKING CONVERSATION
# -------------------------------------------------------

@app.post("/api/booking")
def create_booking(request: BookingRequest):

    try:

        session_id = request.session_id.strip()
        user_message = request.prompt.strip()

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
                "seat_preference": None,
                "awaiting_theatre_selection": False,
                "available_theatres": []
            }
        )

        if previous_booking.get("confirmed_booking"):

            return {
                "status": "success",
                "booking": previous_booking
            }

        # HANDLE YES AFTER THEATRE ALTERNATIVE PROMPT

        if (
            previous_booking.get("awaiting_theatre_selection")
            and len(previous_booking.get("available_theatres", [])) == 1
            and user_message.lower() in [
                "yes", "yeah", "ok", "okay",
                "sure", "select it", "choose it"
            ]
        ):

            selected_theatre = (
                previous_booking["available_theatres"][0]
            )

            booking_data = {
                "movie": previous_booking.get("movie"),
                "date": previous_booking.get("date"),
                "time": previous_booking.get("time"),
                "theatre": selected_theatre,
                "tickets": previous_booking.get("tickets"),
                "seat_preference": previous_booking.get(
                    "seat_preference"
                ),
                "missing_details": [],
                "ready_to_book": True,
                "reply": (
                    f"You selected {selected_theatre}. "
                    "Checking the showtime now."
                )
            }

        else:

            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=f"""
You are CineMate AI, a movie booking assistant.

Previous booking:
{json.dumps(previous_booking)}

New user message:
{user_message}

Update the booking.

Rules:
1. Preserve previous details unless changed.
2. Extract new details from the user message.
3. Never invent details.
4. Required fields: movie, date, time, theatre, tickets.
5. Seat preference is optional.
6. Ask only for missing details.
7. Return tickets as a number.

Return ONLY JSON:

{{
  "movie": null,
  "date": null,
  "time": null,
  "theatre": null,
  "tickets": null,
  "seat_preference": null,
  "missing_details": [],
  "ready_to_book": false,
  "reply": "Friendly response"
}}
""",
                config={
                    "response_mime_type": "application/json"
                }
            )

            booking_data = json.loads(response.text)

        # PRESERVE PREVIOUS DETAILS

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

        if booking_data.get("tickets") is not None:

            try:
                booking_data["tickets"] = int(
                    booking_data["tickets"]
                )
            except (TypeError, ValueError):
                booking_data["tickets"] = None

        required_fields = [
            "movie", "date", "time", "theatre", "tickets"
        ]

        booking_data["missing_details"] = [
            field
            for field in required_fields
            if not booking_data.get(field)
        ]

        booking_data["ready_to_book"] = (
            len(booking_data["missing_details"]) == 0
        )

        if not booking_data["ready_to_book"]:

            booking_sessions[session_id] = {
                **{
                    field: booking_data.get(field)
                    for field in fields
                },
                "awaiting_theatre_selection": False,
                "available_theatres": []
            }

            return {
                "status": "success",
                "booking": booking_data
            }

        # CHECK THEATRE

        showtime_result = search_showtimes(
            movie=booking_data["movie"],
            theatre=booking_data["theatre"],
            date=booking_data["date"]
        )

        if not showtime_result.get("available"):

            available_theatres = (
                showtime_result.get("available_theatres", [])
            )

            booking_data["ready_to_book"] = False
            booking_data["show_id"] = None
            booking_data["available_theatres"] = available_theatres
            booking_data["missing_details"] = [
                "theatre_selection"
            ]

            if available_theatres:

                booking_data["reply"] = (
                    f"{booking_data['theatre']} is unavailable. "
                    "Available demo theatres: "
                    f"{', '.join(available_theatres)}. "
                    "Would you like to select "
                    f"{available_theatres[0]}?"
                )

            else:

                booking_data["reply"] = (
                    "No supported demo theatres are available."
                )

            booking_sessions[session_id] = {
                **{
                    field: booking_data.get(field)
                    for field in fields
                },
                "awaiting_theatre_selection": bool(
                    available_theatres
                ),
                "available_theatres": available_theatres
            }

            return {
                "status": "success",
                "booking": booking_data
            }

        # MATCH SHOWTIME

        requested_time = normalize_time(
            str(booking_data["time"])
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

            available_times = [
                show["time"]
                for show in showtime_result["showtimes"]
            ]

            booking_data["ready_to_book"] = False
            booking_data["available_showtimes"] = available_times
            booking_data["missing_details"] = [
                "showtime_selection"
            ]

            booking_data["reply"] = (
                "Requested showtime unavailable. Available times: "
                f"{', '.join(available_times)}."
            )

            booking_sessions[session_id] = {
                **{
                    field: booking_data.get(field)
                    for field in fields
                },
                "awaiting_theatre_selection": False,
                "available_theatres": []
            }

            return {
                "status": "success",
                "booking": booking_data
            }

        # VALID SHOW

        booking_data["theatre"] = showtime_result["theatre"]
        booking_data["time"] = selected_show["time"]
        booking_data["show_id"] = selected_show["show_id"]
        booking_data["available_theatres"] = (
            showtime_result["available_theatres"]
        )

        booking_data["agent_response"] = run_booking_agent(
            booking_data
        )

        booking_data["ready_to_book"] = True
        booking_data["missing_details"] = []

        booking_sessions[session_id] = {
            **booking_data,
            "awaiting_theatre_selection": False
        }

        return {
            "status": "success",
            "booking": booking_data
        }

    except HTTPException:
        raise

    except Exception as error:

        print("Booking conversation error:", str(error))

        raise HTTPException(
            status_code=500,
            detail=f"Gemini API error: {str(error)}"
        )


# -------------------------------------------------------
# CONFIRM SIMULATED BOOKING
# -------------------------------------------------------

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
                detail="Booking session not found."
            )

        if booking.get("confirmed_booking"):

            return {
                "status": "success",
                "message": "This booking was already confirmed.",
                "simulation": True,
                "booking": booking["confirmed_booking"]
            }

        required_fields = [
            "movie", "theatre", "date", "time", "tickets"
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

        selected_preference = (
            request.seat_preference
            or booking.get("seat_preference")
            or "middle"
        ).strip().lower()

        if selected_preference not in SEATS_BY_PREFERENCE:
            raise HTTPException(
                status_code=400,
                detail="Choose front, middle or back seating."
            )

        selected_seats = request.selected_seats

        if not selected_seats:
            raise HTTPException(
                status_code=400,
                detail="Please select your seats before confirming."
            )

        if len(selected_seats) != tickets:
            raise HTTPException(
                status_code=400,
                detail=f"Please select exactly {tickets} seats."
            )

        if len(set(selected_seats)) != len(selected_seats):
            raise HTTPException(
                status_code=400,
                detail="Duplicate seat selection is not allowed."
            )

        valid_section_seats = set(
            SEATS_BY_PREFERENCE[selected_preference]
        )

        invalid_seats = [
            seat
            for seat in selected_seats
            if seat not in valid_section_seats
        ]

        if invalid_seats:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Selected seats do not belong to the chosen section.",
                    "invalid_seats": invalid_seats
                }
            )

        showtime_result = search_showtimes(
            movie=booking["movie"],
            theatre=booking["theatre"],
            date=booking["date"]
        )

        if not showtime_result.get("available"):
            raise HTTPException(
                status_code=400,
                detail="Selected theatre is unavailable."
            )

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
                detail="Requested showtime is unavailable."
            )

        show_id = selected_show["show_id"]

        booked_seats = set(
            get_booked_seats(show_id)
        )

        unavailable_seats = [
            seat
            for seat in selected_seats
            if seat in booked_seats
        ]

        if unavailable_seats:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Some selected seats are no longer available.",
                    "unavailable_seats": unavailable_seats
                }
            )

        result = create_simulated_booking(
            movie=booking["movie"],
            theatre=booking["theatre"],
            date=booking["date"],
            time=selected_show["time"],
            tickets=tickets,
            seats=selected_seats,
            show_id=show_id
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=409,
                detail=result.get("message", "Booking failed.")
            )

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

        print("Booking confirmation error:", str(error))

        raise HTTPException(
            status_code=500,
            detail="Booking confirmation failed."
        )


# -------------------------------------------------------
# GET SEAT AVAILABILITY
# -------------------------------------------------------

@app.get("/api/seats/{show_id}")
def get_seat_availability(show_id: str):

    if (
        len(show_id) != 64
        or any(
            character not in "0123456789abcdef"
            for character in show_id
        )
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid show ID."
        )

    booked = set(
        get_booked_seats(show_id)
    )

    return {
        "status": "success",
        "simulation": True,
        "show_id": show_id,
        "sections": {
            preference: {
                "total": len(seats),
                "available": [
                    seat
                    for seat in seats
                    if seat not in booked
                ],
                "booked": [
                    seat
                    for seat in seats
                    if seat in booked
                ]
            }
            for preference, seats in SEATS_BY_PREFERENCE.items()
        }
    }


# -------------------------------------------------------
# LOOK UP SIMULATED BOOKING
# -------------------------------------------------------

@app.get("/api/booking/{booking_id}")
def get_simulated_booking(booking_id: str):

    with get_db() as connection:

        row = connection.execute(
            """
            SELECT booking_data
            FROM simulated_bookings
            WHERE booking_id = %s
            """,
            (booking_id,)
        ).fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Simulated booking not found."
        )

    return {
        "status": "success",
        "simulation": True,
        "booking": row["booking_data"]
    }