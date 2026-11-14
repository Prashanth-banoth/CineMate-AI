"use client";

import { useState } from "react";

type Booking = {
  movie: string | null;
  date: string | null;
  time: string | null;
  theatre: string | null;
  tickets: number | null;
  seat_preference: string | null;
  missing_details: string[];
  ready_to_book: boolean;
  reply: string;
  agent_response?: string;
};

type Message = {
  role: "user" | "ai";
  text: string;
};

type Movie = {
  Title: string;
  Year: string;
  imdbID: string;
  Type: string;
  Poster: string;
};

type ConfirmedBooking = {
  booking_id: string;
  movie: string;
  theatre: string;
  date: string;
  time: string;
  tickets: number;
  seats: string[];
  show_id: string;
  status: string;
  simulation: boolean;
};

const API_URL = "https://cinemate-ai-backend.onrender.com";

export default function Home() {
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [booking, setBooking] = useState<Booking | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [error, setError] = useState("");

  const [sessionId] = useState(() => `session-${Date.now()}`);

  const [seatPreference, setSeatPreference] = useState("Middle");
  const [confirmedBooking, setConfirmedBooking] =
    useState<ConfirmedBooking | null>(null);

  // Movie search states
  const [movieTitle, setMovieTitle] = useState("");
  const [movies, setMovies] = useState<Movie[]>([]);
  const [movieLoading, setMovieLoading] = useState(false);
  const [movieError, setMovieError] = useState("");

  async function searchMovies() {
    if (!movieTitle.trim() || movieLoading) return;

    setMovieLoading(true);
    setMovieError("");
    setMovies([]);

    try {
      const res = await fetch(
        `${API_URL}/api/movies/search?title=${encodeURIComponent(
          movieTitle.trim()
        )}`
      );

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Movie search failed.");
      }

      if (data.Response === "False") {
        setMovieError(data.Error || "No movies found.");
        return;
      }

      setMovies(data.Search || []);
    } catch (error) {
      setMovieError(
        error instanceof Error
          ? error.message
          : "Unable to connect to movie search."
      );
    } finally {
      setMovieLoading(false);
    }
  }

  function selectMovie(movie: Movie) {
    setPrompt(`I want to book tickets for ${movie.Title}`);
    setMovieTitle(movie.Title);
    setMessages((previous) => [
      ...previous,
      {
        role: "ai",
        text: `${movie.Title} selected. Now tell me your booking details.`,
      },
    ]);

    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleBooking() {
    if (!prompt.trim() || loading || confirmLoading || confirmedBooking) return;

    const userPrompt = prompt.trim();

    setMessages((previous) => [
      ...previous,
      { role: "user", text: userPrompt },
    ]);

    setPrompt("");
    setLoading(true);
    setError("");

    try {
      const res = await fetch(`${API_URL}/api/booking`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          prompt: userPrompt,
          session_id: sessionId,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Something went wrong while preparing your booking."
        );
      }

      const bookingData: Booking = data.booking;

      setBooking(bookingData);

      if (bookingData.seat_preference) {
        const preference =
          bookingData.seat_preference.charAt(0).toUpperCase() +
          bookingData.seat_preference.slice(1).toLowerCase();
        setSeatPreference(preference);
      }

      setMessages((previous) => [
        ...previous,
        {
          role: "ai",
          text:
            bookingData.reply ||
            data.agent_response ||
            "I have updated your booking details.",
        },
      ]);
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Unable to connect to CineMate AI.";

      setError(message);
      setMessages((previous) => [
        ...previous,
        { role: "ai", text: message },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function confirmBooking() {
    if (
      !booking?.ready_to_book ||
      confirmLoading ||
      confirmedBooking
    ) {
      return;
    }

    setConfirmLoading(true);
    setError("");

    try {
      const res = await fetch(`${API_URL}/api/booking/confirm`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          session_id: sessionId,
          seat_preference: seatPreference.toLowerCase(),
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : data.detail?.message || "Booking confirmation failed."
        );
      }

      const result: ConfirmedBooking = data.booking;

      setConfirmedBooking(result);

      setMessages((previous) => [
        ...previous,
        {
          role: "ai",
          text: `Your simulated booking is confirmed. Booking ID: ${result.booking_id}. Selected seats: ${result.seats.join(
            ", "
          )}.`,
        },
      ]);
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to confirm the simulated booking."
      );
    } finally {
      setConfirmLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#080B14] text-white">
      <nav className="flex items-center justify-between border-b border-white/10 px-8 py-5">
        <h1 className="text-2xl font-bold">
          CineMate<span className="text-violet-400"> AI</span>
        </h1>

        <span className="rounded-full border border-violet-400/30 bg-violet-400/10 px-4 py-2 text-sm text-violet-300">
          Gemini AI Assistant
        </span>
      </nav>

      <section className="mx-auto max-w-5xl px-6 py-14">
        <div className="text-center">
          <div className="mb-6 inline-block rounded-full border border-violet-400/30 bg-violet-400/10 px-5 py-2 text-sm text-violet-300">
            ✨ Smart Movie Booking Experience
          </div>

          <h2 className="text-4xl font-bold sm:text-6xl">
            Your next movie night,
            <span className="block bg-gradient-to-r from-violet-400 to-blue-400 bg-clip-text text-transparent">
              planned by AI.
            </span>
          </h2>

          <p className="mx-auto mt-6 max-w-2xl text-gray-400">
            Discover movies and tell CineMate what you want to watch.
            Your AI assistant will help organize your movie booking.
          </p>
        </div>

        {/* Movie Search Section */}
        <div className="mt-12 rounded-2xl border border-white/10 bg-[#111827] p-6">
          <div className="mb-5">
            <h3 className="text-xl font-semibold">🎬 Discover Movies</h3>
            <p className="mt-2 text-sm text-gray-400">
              Search movies by title and explore their posters and release years.
            </p>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              type="text"
              value={movieTitle}
              onChange={(e) => setMovieTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") searchMovies();
              }}
              placeholder="Search a movie... e.g. Pushpa 2"
              className="min-w-0 flex-1 rounded-xl border border-white/10 bg-[#080B14] px-4 py-3 text-sm outline-none focus:border-violet-400"
            />

            <button
              onClick={searchMovies}
              disabled={movieLoading || !movieTitle.trim()}
              className="rounded-xl bg-violet-600 px-6 py-3 font-semibold transition hover:bg-violet-500 disabled:opacity-50"
            >
              {movieLoading ? "Searching..." : "Search Movies"}
            </button>
          </div>

          {movieError && (
            <p className="mt-5 rounded-lg border border-red-400/20 bg-red-400/10 p-3 text-sm text-red-300">
              {movieError}
            </p>
          )}

          {movies.length > 0 && (
            <div className="mt-7 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {movies.map((movie) => (
                <div
                  key={movie.imdbID}
                  className="overflow-hidden rounded-xl border border-white/10 bg-[#080B14]"
                >
                  {movie.Poster && movie.Poster !== "N/A" ? (
                    <img
                      src={movie.Poster}
                      alt={movie.Title}
                      className="h-64 w-full bg-black object-contain"
                    />
                  ) : (
                    <div className="flex h-64 items-center justify-center bg-[#1a2030] text-gray-500">
                      No poster available
                    </div>
                  )}

                  <div className="p-4">
                    <h4 className="font-semibold">{movie.Title}</h4>

                    <p className="mt-2 text-sm text-gray-400">
                      Release Year: {movie.Year}
                    </p>

                    <p className="mt-1 text-xs text-gray-500">
                      IMDb ID: {movie.imdbID}
                    </p>

                    <button
                      onClick={() => selectMovie(movie)}
                      className="mt-4 w-full rounded-lg bg-violet-600 py-2 text-sm font-semibold transition hover:bg-violet-500"
                    >
                      Select Movie →
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {confirmedBooking ? (
          <div className="mx-auto mt-12 max-w-xl rounded-2xl border border-green-400/30 bg-[#111827] p-8 text-center">
            <div className="text-5xl">🎉</div>

            <h2 className="mt-5 text-2xl font-bold text-green-400">
              Simulated Booking Confirmed!
            </h2>

            <p className="mt-3 text-gray-400">
              CineMate has created your demo booking record.
            </p>

            <div className="mt-6 rounded-xl bg-[#080B14] p-5">
              <p className="text-sm text-gray-400">Booking ID</p>
              <p className="mt-2 text-2xl font-bold text-violet-400">
                {confirmedBooking.booking_id}
              </p>
            </div>

            <div className="mt-5 space-y-2 text-sm text-gray-300">
              <p>{confirmedBooking.movie}</p>
              <p>{confirmedBooking.theatre}</p>
              <p>
                {confirmedBooking.date} · {confirmedBooking.time}
              </p>
              <p>
                {confirmedBooking.tickets} Tickets · Seats:{" "}
                {confirmedBooking.seats.join(", ")}
              </p>
              <p className="text-xs text-gray-500">
                Status: {confirmedBooking.status}
              </p>
            </div>

            <p className="mt-6 text-xs text-gray-500">
              Demo only. No actual cinema tickets have been booked, held or
              paid for.
            </p>
          </div>
        ) : (
          <div className="mt-12 grid gap-8 md:grid-cols-2">
            {/* AI Chat */}
            <div className="rounded-2xl border border-white/10 bg-[#111827] p-5">
              <h3 className="mb-5 text-lg font-semibold">Movie Assistant</h3>

              <div className="mb-5 max-h-80 space-y-4 overflow-y-auto">
                {messages.length === 0 && (
                  <p className="text-sm leading-7 text-gray-400">
                    Hello! I&apos;m CineMate AI. Tell me your movie booking
                    requirements to get started.
                  </p>
                )}

                {messages.map((message, index) => (
                  <div
                    key={index}
                    className={`rounded-xl p-4 text-sm leading-6 ${
                      message.role === "user"
                        ? "ml-8 bg-violet-600"
                        : "mr-4 border border-white/10 bg-[#080B14] text-gray-200"
                    }`}
                  >
                    {message.role === "ai" && (
                      <p className="mb-2 font-semibold text-violet-400">
                        CineMate AI
                      </p>
                    )}
                    {message.text}
                  </div>
                ))}

                {loading && (
                  <p className="text-sm text-violet-300">
                    CineMate AI is thinking...
                  </p>
                )}

                {confirmLoading && (
                  <p className="text-sm text-green-300">
                    Confirming your simulated booking...
                  </p>
                )}
              </div>

              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleBooking();
                  }
                }}
                placeholder="Example: Book 2 tickets for Pushpa 2 tomorrow..."
                className="min-h-28 w-full resize-none rounded-xl border border-white/10 bg-[#080B14] p-4 text-sm outline-none focus:border-violet-400"
              />

              <button
                onClick={handleBooking}
                disabled={
                  loading ||
                  confirmLoading ||
                  !prompt.trim() ||
                  Boolean(confirmedBooking)
                }
                className="mt-3 w-full rounded-xl bg-violet-600 py-3 font-semibold transition hover:bg-violet-500 disabled:opacity-50"
              >
                {loading ? "Processing..." : "Send Message →"}
              </button>
            </div>

            {/* Booking Summary */}
            <div className="rounded-2xl border border-white/10 bg-[#111827] p-5">
              <h3 className="mb-6 text-lg font-semibold">Booking Summary</h3>

              {!booking ? (
                <div className="flex min-h-64 items-center justify-center text-center text-sm text-gray-500">
                  Your booking details will appear here.
                </div>
              ) : (
                <>
                  <div className="space-y-4">
                    {[
                      ["Movie", booking.movie],
                      ["Date", booking.date],
                      ["Showtime", booking.time],
                      ["Theatre", booking.theatre],
                      ["Tickets", booking.tickets],
                    ].map(([label, value]) => (
                      <div
                        key={label}
                        className="flex justify-between gap-4 border-b border-white/10 pb-3 text-sm"
                      >
                        <span className="text-gray-400">{label}</span>
                        <span className="text-right font-medium">
                          {value ?? "Not provided"}
                        </span>
                      </div>
                    ))}
                  </div>

                  {booking.ready_to_book ? (
                    <>
                      <div className="mt-6">
                        <p className="mb-3 text-sm font-semibold">
                          Select seat preference
                        </p>

                        <div className="grid grid-cols-3 gap-2">
                          {["Front", "Middle", "Back"].map((seat) => (
                            <button
                              key={seat}
                              onClick={() => setSeatPreference(seat)}
                              disabled={confirmLoading}
                              className={`rounded-lg border py-3 text-sm transition disabled:opacity-50 ${
                                seatPreference === seat
                                  ? "border-violet-400 bg-violet-600/20 text-violet-300"
                                  : "border-white/10 text-gray-400 hover:border-violet-400"
                              }`}
                            >
                              {seat}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="mt-6 rounded-xl border border-green-400/20 bg-green-400/5 p-4">
                        <p className="text-sm font-semibold text-green-400">
                          All required details collected!
                        </p>
                        <p className="mt-1 text-xs text-gray-400">
                          Review your details and seat preference before
                          confirming.
                        </p>
                      </div>

                      <button
                        onClick={confirmBooking}
                        disabled={confirmLoading || loading}
                        className="mt-5 w-full rounded-xl bg-green-600 py-3 font-semibold transition hover:bg-green-500 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {confirmLoading
                          ? "Confirming..."
                          : "Confirm Booking →"}
                      </button>

                      <p className="mt-3 text-center text-xs text-gray-500">
                        Simulation only. No real tickets or payment.
                      </p>
                    </>
                  ) : (
                    <div className="mt-6 rounded-xl border border-amber-400/20 bg-amber-400/5 p-4">
                      <p className="mb-3 text-sm font-semibold text-amber-400">
                        Waiting for details
                      </p>

                      {booking.missing_details.map((detail) => (
                        <p key={detail} className="text-sm text-gray-400">
                          • {detail}
                        </p>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )}

        {error && (
          <p className="mx-auto mt-6 max-w-2xl rounded-lg border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-300">
            {error}
          </p>
        )}
      </section>

      <footer className="border-t border-white/10 py-6 text-center text-sm text-gray-600">
        © 2026 CineMate AI. Your personal movie booking assistant.
      </footer>
    </main>
  );
}
