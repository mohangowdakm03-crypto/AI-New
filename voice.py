from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional

from timer import CountdownDisplay

try:
    import speech_recognition as sr
except ImportError:
    sr = None  # type: ignore[assignment]


@dataclass(frozen=True)
class VoiceInputResult:
    answer: str
    time_taken: float
    used_voice: bool
    timed_out: bool
    error: Optional[str] = None


def voice_input_available() -> bool:
    return sr is not None


def capture_voice_input(time_limit: int = 60, start_timeout: int = 8) -> VoiceInputResult:
    """
    Attempt voice capture first, then let the caller decide whether to fall
    back to text input if capture or recognition fails.
    """
    if sr is None:
        return VoiceInputResult(
            answer="",
            time_taken=0.0,
            used_voice=False,
            timed_out=False,
            error="speech_recognition is not installed, so voice mode is unavailable.",
        )

    recognizer = sr.Recognizer()
    start = time.monotonic()

    try:
        with sr.Microphone() as source:
            print("Voice mode: start speaking when ready.")
            remaining = max(1, time_limit)
            display = CountdownDisplay("Voice timer", remaining)
            stop_event = threading.Event()

            def _countdown() -> None:
                while not stop_event.is_set():
                    elapsed = time.monotonic() - start
                    seconds_left = max(0, remaining - int(elapsed))
                    display.render(seconds_left, "Listening...")
                    if seconds_left <= 0:
                        break
                    time.sleep(1)

            countdown_thread = threading.Thread(target=_countdown, daemon=True)
            countdown_thread.start()
            try:
                audio = recognizer.listen(
                    source,
                    timeout=min(start_timeout, remaining),
                    phrase_time_limit=remaining,
                )
            except sr.WaitTimeoutError:
                display.clear()
                elapsed = min(time.monotonic() - start, float(time_limit))
                return VoiceInputResult(
                    answer="",
                    time_taken=elapsed,
                    used_voice=False,
                    timed_out=elapsed >= time_limit,
                    error="No speech detected in time.",
                )
            finally:
                stop_event.set()
                countdown_thread.join(timeout=0.2)
                display.clear()

    except (OSError, AttributeError) as exc:
        return VoiceInputResult(
            answer="",
            time_taken=0.0,
            used_voice=False,
            timed_out=False,
            error=f"Microphone not available: {exc}",
        )
    except Exception as exc:
        return VoiceInputResult(
            answer="",
            time_taken=0.0,
            used_voice=False,
            timed_out=False,
            error=(
                "Voice input could not be initialized. "
                f"Check microphone dependencies such as PyAudio/PortAudio. Details: {exc}"
            ),
        )

    elapsed = min(time.monotonic() - start, float(time_limit))
    try:
        answer = recognizer.recognize_google(audio).strip()
    except sr.UnknownValueError:
        return VoiceInputResult(
            answer="",
            time_taken=elapsed,
            used_voice=False,
            timed_out=False,
            error="Could not understand the audio clearly.",
        )
    except sr.RequestError as exc:
        return VoiceInputResult(
            answer="",
            time_taken=elapsed,
            used_voice=False,
            timed_out=False,
            error=f"Voice recognition request failed: {exc}",
        )

    return VoiceInputResult(
        answer=answer,
        time_taken=elapsed,
        used_voice=True,
        timed_out=elapsed >= time_limit,
        error=None,
    )
