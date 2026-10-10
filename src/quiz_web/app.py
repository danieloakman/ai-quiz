"""FastAPI app: topic browse + deterministic play."""

from __future__ import annotations

from pathlib import Path

from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from quiz_data.errors import QuizDataError
from quiz_data.questions import build_question
from quiz_data.sample import DIFFICULTIES
from quiz_data.store import list_topic_slugs, load_topic_meta, topic_status
from quiz_web.sessions import PlaySession, SessionStore, new_session_id

_PKG = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(_PKG / "templates"))
sessions = SessionStore()

app = FastAPI(title="ai-quiz", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(_PKG / "static")), name="static")


def create_app() -> FastAPI:
    return app


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
    return {
        "id": session.id,
        "topic": session.topic,
        "title": session.title,
        "formats": session.formats,
        "questions_total": session.questions_total,
        "difficulty": session.difficulty,
        "score": session.score,
        "answered": session.answered,
        "remaining": max(0, session.questions_total - session.answered),
        "finished": session.finished,
        "question": (
            _public_question(session.current)
            if session.current and not session.finished
            else None
        ),
        "last_result": session.last_result,
        "history": session.history,
    }


def _deal(session: PlaySession) -> None:
    if session.answered >= session.questions_total:
        session.finished = True
        session.current = None
        return
    session.current = build_question(
        session.topic,
        session.difficulty,
        session.formats,
    )


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
        },
    )


@app.post("/play")
def start_play(
    topic: Annotated[str, Form()],
    questions: Annotated[int, Form()] = 5,
    difficulty: Annotated[str, Form()] = "moderate",
    formats: Annotated[list[str] | None, Form()] = None,
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

    if not formats:
        formats = ["mcq", "yes-no"]
    formats = [f.strip().lower() for f in formats if f.strip()]
    if not formats:
        formats = ["mcq", "yes-no"]

    session = PlaySession(
        id=new_session_id(),
        topic=topic,
        title=meta["title"],
        formats=formats,
        questions_total=questions,
        difficulty=difficulty,
    )
    try:
        _deal(session)
    except QuizDataError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from None
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
def answer_play(session_id: str, answer: str = Form(...)):
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.finished or session.current is None:
        raise HTTPException(status_code=400, detail="No active question.")

    q = session.current
    chosen = answer.strip()
    correct = chosen == q.correct
    if correct:
        session.score += 1
    session.answered += 1
    result = {
        "correct": correct,
        "chosen": chosen,
        "expected": q.correct,
        "explanation": q.explanation,
        "prompt": q.prompt,
        "format": q.format,
    }
    session.last_result = result
    session.history.append(result)
    session.current = None

    if session.answered >= session.questions_total:
        session.finished = True
    else:
        try:
            _deal(session)
        except QuizDataError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from None

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
    # Apply to next deal: if a question is already showing, rebuild it
    # only when unanswered — mid-run means next question. Keep current.
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
    formats = payload.get("formats") or ["mcq", "yes-no"]
    if isinstance(formats, str):
        formats = [formats]

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

    session = PlaySession(
        id=new_session_id(),
        topic=topic,
        title=meta["title"],
        formats=[str(f).strip().lower() for f in formats],
        questions_total=questions,
        difficulty=difficulty,
    )
    try:
        _deal(session)
    except QuizDataError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from None
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
    if session.finished or session.current is None:
        raise HTTPException(status_code=400, detail="No active question.")

    q = session.current
    chosen = str(payload.get("answer", "")).strip()
    correct = chosen == q.correct
    if correct:
        session.score += 1
    session.answered += 1
    result = {
        "correct": correct,
        "chosen": chosen,
        "expected": q.correct,
        "explanation": q.explanation,
        "prompt": q.prompt,
        "format": q.format,
    }
    session.last_result = result
    session.history.append(result)
    session.current = None

    if session.answered >= session.questions_total:
        session.finished = True
    else:
        try:
            _deal(session)
        except QuizDataError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from None

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
