
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
};

type Message = {
  role: "user" | "ai";
  text: string;
};

export default function Home() {
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [booking, setBooking] = useState<Booking | null>(null);
  const [loading, setLoading] = useState(false);

  const [sessionId] = useState(
    () => `session-${Date.now()}`
  );

  const [seatPreference, setSeatPreference] = useState("Middle");
  const [confirmed, setConfirmed] = useState(false);
  const [bookingId, setBookingId] = useState("");

  async function handleBooking() {
    if (!prompt.trim() || loading || confirmed) return;

    const userPrompt = prompt.trim();

    setMessages((previous) => [
      ...previous,
      { role: "user", text: userPrompt },
    ]);

    setPrompt("");
    setLoading(true);

    try {
      const res = await fetch("http://127.0.0.1:8000/api/booking", {
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
        throw new Error(data.detail || "Something went wrong");
      }

      const bookingData: Booking = data.booking;

      setBooking(bookingData);

      setMessages((previous) => [
        ...previous,
        { role: "ai", text: bookingData.reply },
      ]);
    } catch (error) {
      setMessages((previous) => [
        ...previous,
        {
          role: "ai",
          text:
            error instanceof Error
              ? error.message
              : "Unable to connect to CineMate AI.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function confirmBooking() {
    if (!booking?.ready_to_book || confirmed) return;

    const id = `CM-${Date.now().toString().slice(-8)}`;

    setBookingId(id);
    setConfirmed(true);
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
            Tell CineMate what you want to watch. Your AI assistant
            will help organize your movie booking.
          </p>
        </div>

        {confirmed ? (
          <div className="mx-auto mt-12 max-w-xl rounded-2xl border border-green-400/30 bg-[#111827] p-8 text-center">
            <div className="text-5xl">🎉</div>

            <h2 className="mt-5 text-2xl font-bold text-green-400">
              Booking Confirmed!
            </h2>

            <p className="mt-3 text-gray-400">
              Your simulated movie booking has been created successfully.
            </p>

            <div className="mt-6 rounded-xl bg-[#080B14] p-5">
              <p className="text-sm text-gray-400">
                Booking ID
              </p>
              <p className="mt-2 text-2xl font-bold text-violet-400">
                {bookingId}
              </p>
            </div>

            <div className="mt-5 space-y-2 text-sm text-gray-300">
              <p>{booking?.movie}</p>
              <p>{booking?.theatre}</p>
              <p>{booking?.date} · {booking?.time}</p>
              <p>{booking?.tickets} Tickets · {seatPreference} seats</p>
            </div>

            <p className="mt-6 text-xs text-gray-500">
              Demo confirmation only. No actual tickets have been booked.
            </p>
          </div>
        ) : (
          <div className="mt-12 grid gap-8 md:grid-cols-2">
            <div className="rounded-2xl border border-white/10 bg-[#111827] p-5">
              <h3 className="mb-5 text-lg font-semibold">
                Movie Assistant
              </h3>

              <div className="mb-5 max-h-80 space-y-4 overflow-y-auto">
                {messages.length === 0 && (
                  <p className="text-sm leading-7 text-gray-400">
                    Hello! I'm CineMate AI. Tell me your movie booking
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
                disabled={loading || !prompt.trim()}
                className="mt-3 w-full rounded-xl bg-violet-600 py-3 font-semibold transition hover:bg-violet-500 disabled:opacity-50"
              >
                {loading ? "Processing..." : "Send Message →"}
              </button>
            </div>

            <div className="rounded-2xl border border-white/10 bg-[#111827] p-5">
              <h3 className="mb-6 text-lg font-semibold">
                Booking Summary
              </h3>

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
                              className={`rounded-lg border py-3 text-sm transition ${
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
                          Review your details before confirming.
                        </p>
                      </div>

                      <button
                        onClick={confirmBooking}
                        className="mt-5 w-full rounded-xl bg-green-600 py-3 font-semibold transition hover:bg-green-500"
                      >
                        Confirm Booking →
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
      </section>

      <footer className="border-t border-white/10 py-6 text-center text-sm text-gray-600">
        © 2026 CineMate AI. Your personal movie booking assistant.
      </footer>
    </main>
  );
}
