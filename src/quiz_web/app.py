"""FastAPI app: topic browse + agent-hosted play."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from quiz_data.errors import QuizDataError
from quiz_data.sample import DIFFICULTIES, sample_for_question
from quiz_data.store import list_topic_slugs, load_topic_meta, topic_status
from quiz_host.errors import QuizHostError
from quiz_host.factory import host_from_env
from quiz_host.parse import normalize_formats
from quiz_host.protocols import FORMATS, BuiltQuestion, GradeResult, QuizHost
from quiz_web.sessions import PlaySession, SessionStore, new_session_id

_TIME_LIMIT_MAX = 600

_PKG = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(_PKG / "templates"))
sessions = SessionStore()
_host: QuizHost | None = None

app = FastAPI(title="ai-quiz", version="0.2.0")
app.mount("/static", StaticFiles(directory=str(_PKG / "static")), name="static")


def create_app() -> FastAPI:
    return app


def get_host() -> QuizHost:
    global _host
    if _host is None:
        _host = host_from_env()
    return _host


def set_host(host: QuizHost | None) -> None:
    global _host
    _host = host


def main() -> None:
    import uvicorn

    uvicorn.run("quiz_web.app:app", host="127.0.0.1", port=8765, reload=True)


def _serialize_status(st: dict) -> dict:
    out = dict(st)
    out["subtopics"] = [
        {
            "slug": s.slug,
            "fact_count": s.fact_count,
            "glossary_count": s.glossary_count,
            "ready": s.ready,
            "hard_mcq_ok": s.hard_mcq_ok,
            "label": s.label,
        }
        for s in st["subtopics"]
    ]
    return out


def _public_question(q) -> dict:
    return {
        "format": q.format,
        "prompt": q.prompt,
        "options": q.options,
        "subtopic": q.subtopic,
        "difficulty": q.difficulty,
    }


def _session_view(session: PlaySession) -> dict:
    with session.lock:
        dealing = session.dealing
        deal_error = session.deal_error
        current = session.current
        finished = session.finished
        last_result = session.last_result
        history = list(session.history)
        score = session.score
        answered = session.answered
        difficulty = session.difficulty
        formats = list(session.formats)
        questions_total = session.questions_total
        time_limit_seconds = session.time_limit_seconds

    return {
        "id": session.id,
        "topic": session.topic,
        "title": session.title,
        "formats": formats,
        "questions_total": questions_total,
        "difficulty": difficulty,
        "time_limit_seconds": time_limit_seconds,
        "score": score,
        "answered": answered,
        "remaining": max(0, questions_total - answered),
        "finished": finished,
        "dealing": dealing,
        "deal_error": deal_error,
        "question": (_public_question(current) if current and not finished else None),
        "last_result": last_result,
        "history": history,
    }


def _deal(session: PlaySession) -> None:
    if session.answered >= session.questions_total:
        session.finished = True
        session.current = None
        return
    sample = sample_for_question(session.topic, session.difficulty)
    session.current = get_host().deal(sample, session.formats)


def _exc_message(error: BaseException) -> str:
    if isinstance(error, (QuizHostError, QuizDataError)):
        return error.message
    return str(error)


def _apply_prefetched(
    session: PlaySession,
    question: BuiltQuestion | None,
    error: BaseException | None,
) -> None:
    with session.lock:
        session.dealing = False
        if error is not None:
            session.deal_error = _exc_message(error)
            return
        session.deal_error = None
        session.current = question


def _grade_and_prefetch(
    session: PlaySession,
    chosen: str,
    *,
    timed_out: bool = False,
) -> None:
    """Grade the current answer; prefetch the next question in parallel."""
    q = session.current
    assert q is not None
    host = get_host()
    will_continue = session.answered + 1 < session.questions_total

    box: dict = {"question": None, "error": None, "done": False}
    deal_thread: threading.Thread | None = None

    if will_continue:
        topic = session.topic
        difficulty = session.difficulty
        formats = list(session.formats)

        def deal_worker() -> None:
            try:
                sample = sample_for_question(topic, difficulty)
                box["question"] = host.deal(sample, formats)
            except BaseException as exc:  # noqa: BLE001
                box["error"] = exc
            finally:
                box["done"] = True

        with session.lock:
            session.dealing = True
            session.deal_error = None
        deal_thread = threading.Thread(target=deal_worker, daemon=True)
        deal_thread.start()

    if timed_out:
        result_grade = GradeResult(
            correct=False,
            explanation="Time ran out.",
        )
        chosen_display = "(no answer)"
    else:
        result_grade = host.grade(q, chosen)
        chosen_display = chosen

    with session.lock:
        if result_grade.correct:
            session.score += 1
        session.answered += 1
        result = {
            "correct": result_grade.correct,
            "chosen": chosen_display,
            "expected": q.correct,
            "explanation": result_grade.explanation,
            "prompt": q.prompt,
            "format": q.format,
            "timed_out": timed_out,
        }
        session.last_result = result
        session.history.append(result)
        session.current = None

        if not will_continue:
            session.finished = True
            session.dealing = False
            return

        session.finished = False

        if box["done"]:
            err = box["error"]
            session.dealing = False
            if err is not None:
                session.deal_error = _exc_message(err)
            else:
                session.current = box["question"]
                session.deal_error = None
            return

    # Deal still running: finish applying on that thread.
    assert deal_thread is not None

    def finish() -> None:
        deal_thread.join()
        _apply_prefetched(session, box["question"], box["error"])

    threading.Thread(target=finish, daemon=True).start()


def _parse_formats(raw: list[str] | None) -> list[str]:
    if not raw:
        return list(FORMATS)
    try:
        return normalize_formats(raw)
    except QuizHostError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from None


def _parse_time_limit(raw: object) -> int | None:
    if raw is None or raw is False:
        return None
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        raw = text
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="time_limit_seconds must be a positive integer.",
        ) from None
    if value < 1 or value > _TIME_LIMIT_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"time_limit_seconds must be 1–{_TIME_LIMIT_MAX}.",
        )
    return value


def _truthy_flag(raw: object) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return False
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _http_host_error(exc: Exception) -> HTTPException:
    if isinstance(exc, QuizHostError):
        return HTTPException(status_code=502, detail=exc.message)
    if isinstance(exc, QuizDataError):
        return HTTPException(status_code=400, detail=exc.message)
    return HTTPException(status_code=500, detail=str(exc))


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    topics = []
    for slug in list_topic_slugs():
        st = topic_status(slug)
        topics.append(st)
    return templates.TemplateResponse(
        request,
        "home.html",
        {"topics": topics},
    )


@app.get("/topics/{slug}", response_class=HTMLResponse)
def topic_detail(request: Request, slug: str) -> HTMLResponse:
    try:
        st = topic_status(slug)
    except QuizDataError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from None
    return templates.TemplateResponse(
        request,
        "topic.html",
        {
            "topic": st,
            "difficulties": DIFFICULTIES,
            "formats": FORMATS,
        },
    )


@app.post("/play")
def start_play(
    topic: Annotated[str, Form()],
    questions: Annotated[int, Form()] = 5,
    difficulty: Annotated[str, Form()] = "moderate",
    formats: Annotated[list[str] | None, Form()] = None,
    time_limit_seconds: Annotated[str | None, Form()] = None,
):
    try:
        meta = load_topic_meta(topic)
        st = topic_status(topic)
    except QuizDataError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from None

    if st["ready_subtopics"] < 1:
        raise HTTPException(
            status_code=400,
            detail="No ready subtopics. Research more before playing.",
        )
    if questions < 1 or questions > 50:
        raise HTTPException(status_code=400, detail="Questions must be 1–50.")
    difficulty = difficulty.strip().lower()
    if difficulty not in DIFFICULTIES:
        raise HTTPException(status_code=400, detail="Invalid difficulty.")

    fmt_list = _parse_formats(formats)
    limit = _parse_time_limit(time_limit_seconds)

    session = PlaySession(
        id=new_session_id(),
        topic=topic,
        title=meta["title"],
        formats=fmt_list,
        questions_total=questions,
        difficulty=difficulty,
        time_limit_seconds=limit,
    )
    try:
        _deal(session)
    except (QuizDataError, QuizHostError) as exc:
        raise _http_host_error(exc) from None
    sessions.create(session)
    return RedirectResponse(url=f"/play/{session.id}", status_code=303)


@app.get("/play/{session_id}", response_class=HTMLResponse)
def play_page(request: Request, session_id: str) -> HTMLResponse:
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return templates.TemplateResponse(
        request,
        "play.html",
        {
            "session": _session_view(session),
            "difficulties": DIFFICULTIES,
        },
    )


@app.post("/play/{session_id}/answer")
def answer_play(
    session_id: str,
    answer: Annotated[str, Form()] = "",
    timed_out: Annotated[str | None, Form()] = None,
):
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.finished or session.dealing or session.current is None:
        raise HTTPException(status_code=400, detail="No active question.")

    out = _truthy_flag(timed_out)
    if out and session.time_limit_seconds is None:
        raise HTTPException(
            status_code=400,
            detail="This round has no time limit.",
        )

    try:
        _grade_and_prefetch(session, answer.strip(), timed_out=out)
    except (QuizDataError, QuizHostError) as exc:
        raise _http_host_error(exc) from None

    return RedirectResponse(url=f"/play/{session.id}", status_code=303)


@app.post("/play/{session_id}/difficulty")
def set_difficulty(session_id: str, difficulty: str = Form(...)):
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    difficulty = difficulty.strip().lower()
    if difficulty not in DIFFICULTIES:
        raise HTTPException(status_code=400, detail="Invalid difficulty.")
    session.difficulty = difficulty
    return RedirectResponse(url=f"/play/{session.id}", status_code=303)


# --- JSON API (testable) ---


@app.get("/api/topics")
def api_topics():
    return [_serialize_status(topic_status(slug)) for slug in list_topic_slugs()]


@app.get("/api/topics/{slug}")
def api_topic(slug: str):
    try:
        return _serialize_status(topic_status(slug))
    except QuizDataError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from None


@app.post("/api/play")
def api_start_play(payload: dict):
    topic = str(payload.get("topic", "")).strip()
    questions = int(payload.get("questions", 5))
    difficulty = str(payload.get("difficulty", "moderate")).strip().lower()
    formats = payload.get("formats")
    if isinstance(formats, str):
        formats = [formats]
    limit = _parse_time_limit(payload.get("time_limit_seconds"))

    try:
        meta = load_topic_meta(topic)
        st = topic_status(topic)
    except QuizDataError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from None
    if st["ready_subtopics"] < 1:
        raise HTTPException(status_code=400, detail="No ready subtopics.")
    if questions < 1 or questions > 50:
        raise HTTPException(status_code=400, detail="Questions must be 1–50.")
    if difficulty not in DIFFICULTIES:
        raise HTTPException(status_code=400, detail="Invalid difficulty.")

    fmt_list = _parse_formats(formats)

    session = PlaySession(
        id=new_session_id(),
        topic=topic,
        title=meta["title"],
        formats=fmt_list,
        questions_total=questions,
        difficulty=difficulty,
        time_limit_seconds=limit,
    )
    try:
        _deal(session)
    except (QuizDataError, QuizHostError) as exc:
        raise _http_host_error(exc) from None
    sessions.create(session)
    return _session_view(session)


@app.get("/api/play/{session_id}")
def api_get_play(session_id: str):
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return _session_view(session)


@app.post("/api/play/{session_id}/answer")
def api_answer(session_id: str, payload: dict):
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.finished or session.dealing or session.current is None:
        raise HTTPException(status_code=400, detail="No active question.")

    out = _truthy_flag(payload.get("timed_out"))
    if out and session.time_limit_seconds is None:
        raise HTTPException(
            status_code=400,
            detail="This round has no time limit.",
        )

    chosen = str(payload.get("answer", "")).strip()
    try:
        _grade_and_prefetch(session, chosen, timed_out=out)
    except (QuizDataError, QuizHostError) as exc:
        raise _http_host_error(exc) from None

    return _session_view(session)


@app.post("/api/play/{session_id}/difficulty")
def api_difficulty(session_id: str, payload: dict):
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    difficulty = str(payload.get("difficulty", "")).strip().lower()
    if difficulty not in DIFFICULTIES:
        raise HTTPException(status_code=400, detail="Invalid difficulty.")
    session.difficulty = difficulty
    return _session_view(session)
