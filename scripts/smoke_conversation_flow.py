import argparse
import json
import urllib.error
import urllib.request
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test the running conversation/activity API.",
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--user-id", default="smoke-learner")
    parser.add_argument("--token", default="")
    parser.add_argument(
        "--soft",
        action="store_true",
        help="Print report but return exit code 0 even when checks fail.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = ApiClient(args.base_url, args.token)
    checks: list[dict[str, Any]] = []

    conversation = run_check(
        checks,
        "create_conversation",
        lambda: client.post("/api/conversations", {"user_id": args.user_id}),
    )
    conversation_id = str(conversation.get("conversation_id") or "")

    practice_turn = run_check(
        checks,
        "practice_turn",
        lambda: client.post(
            f"/api/conversations/{conversation_id}/messages",
            {
                "user_id": args.user_id,
                "message": "Cho toi 2 cau passive voice.",
            },
        ),
        require=lambda payload: (
            payload.get("intent") == "PRACTICE"
            and payload.get("ui_action") == "practice.start"
            and bool(payload.get("activity", {}).get("activity_id"))
        ),
    )
    activity = practice_turn.get("activity") or {}
    activity_id = str(activity.get("activity_id") or "")
    answers = answers_with_one_mistake(activity.get("exercises") or [])

    run_check(
        checks,
        "get_activity_detail",
        lambda: client.get(f"/api/activities/{activity_id}?user_id={args.user_id}"),
        require=lambda payload: (
            payload.get("activity_id") == activity_id
            and payload.get("ui_action") == "practice.open"
            and bool(payload.get("exercises"))
        ),
    )

    submission = run_check(
        checks,
        "submit_activity",
        lambda: client.post(
            f"/api/activities/{activity_id}/submit",
            {"user_id": args.user_id, "answers": answers},
        ),
        require=lambda payload: (
            payload.get("ui_action") == "practice.result"
            and payload.get("activity", {}).get("activity_id") == activity_id
            and payload.get("result", {}).get("activity_id") == activity_id
        ),
    )

    unsubmitted_turn = run_check(
        checks,
        "create_unsubmitted_context_activity",
        lambda: client.post(
            f"/api/conversations/{conversation_id}/messages",
            {
                "user_id": args.user_id,
                "message": "Cho toi 1 cau vocabulary.",
            },
        ),
        require=lambda payload: (
            payload.get("intent") == "PRACTICE"
            and payload.get("ui_action") == "practice.start"
            and bool(payload.get("activity", {}).get("activity_id"))
            and payload.get("activity", {}).get("activity_id") != activity_id
        ),
    )
    unsubmitted_activity_id = str(
        (unsubmitted_turn.get("activity") or {}).get("activity_id") or "",
    )

    run_check(
        checks,
        "review_latest_submitted_activity",
        lambda: client.post(
            f"/api/conversations/{conversation_id}/messages",
            {"user_id": args.user_id, "message": "Tai sao cau 1 sai?"},
        ),
        require=lambda payload: (
            payload.get("intent") == "REVIEW"
            and payload.get("ui_action") == "review.open"
            and payload.get("activity", {}).get("activity_id") == activity_id
        ),
    )

    run_check(
        checks,
        "get_activity_review",
        lambda: client.get(
            f"/api/activities/{activity_id}/review?user_id={args.user_id}&question_number=1",
        ),
        require=lambda payload: (
            payload.get("activity_id") == activity_id
            and payload.get("ui_action") == "review.open"
            and payload.get("metadata", {}).get("question_number") == 1
        ),
    )

    run_check(
        checks,
        "progress_turn",
        lambda: client.post(
            f"/api/conversations/{conversation_id}/messages",
            {"user_id": args.user_id, "message": "Toi dang yeu phan nao?"},
        ),
        require=lambda payload: (
            payload.get("intent") == "PROGRESS"
            and payload.get("ui_action") == "progress.open"
        ),
    )

    second_conversation = run_check(
        checks,
        "new_chat_keeps_learner_state",
        lambda: client.post("/api/conversations", {"user_id": args.user_id}),
        require=lambda payload: (
            bool(payload.get("conversation_id"))
            and payload.get("conversation_id") != conversation_id
        ),
    )

    run_check(
        checks,
        "learning_focus_choice",
        lambda: client.post(
            f"/api/conversations/{second_conversation.get('conversation_id')}/messages",
            {"user_id": args.user_id, "message": "doc truoc di"},
        ),
        require=lambda payload: (
            payload.get("intent") == "READING"
            and payload.get("ui_action") == "reading.start"
            and payload.get("activity", {}).get("type") == "READING"
            and payload.get("route", {}).get("slots", {}).get("learning_focus")
            == "reading"
        ),
    )

    run_check(
        checks,
        "canonical_learner_progress",
        lambda: client.get(
            f"/api/learners/{args.user_id}/progress?conversation_id={conversation_id}",
        ),
        require=lambda payload: (
            payload.get("learner_id") == args.user_id
            and payload.get("ui_action") == "progress.open"
            and bool(payload.get("summary"))
        ),
    )

    run_check(
        checks,
        "canonical_learner_mastery",
        lambda: client.get(f"/api/learners/{args.user_id}/mastery"),
        require=lambda payload: (
            payload.get("learner_id") == args.user_id
            and payload.get("ui_action") == "mastery.open"
            and bool(payload.get("skill_mastery"))
        ),
    )

    run_check(
        checks,
        "canonical_learner_recommendations",
        lambda: client.get(f"/api/learners/{args.user_id}/recommendations"),
        require=lambda payload: bool(payload.get("recommendations")),
    )

    profile_snapshot = run_check(
        checks,
        "personalization_snapshot",
        lambda: client.get(f"/api/users/{args.user_id}/personalization"),
        require=lambda payload: bool(payload.get("skill_mastery")),
    )

    report = {
        "status": "ok" if all(check["passed"] for check in checks) else "failed",
        "base_url": args.base_url,
        "user_id": args.user_id,
        "conversation_id": conversation_id,
        "second_conversation_id": second_conversation.get("conversation_id"),
        "activity_id": activity_id,
        "unsubmitted_activity_id": unsubmitted_activity_id,
        "generation_run_id": activity.get("generation_run_id"),
        "session_code": submission.get("result", {}).get("session_code"),
        "skill_mastery_count": len(profile_snapshot.get("skill_mastery") or []),
        "checks": checks,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if report["status"] != "ok" and not args.soft:
        raise SystemExit(1)


class ApiClient:
    def __init__(self, base_url: str, token: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def get(self, path: str) -> dict[str, Any]:
        return self._request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, payload)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))


def run_check(
    checks: list[dict[str, Any]],
    name: str,
    fn,
    require=None,
) -> dict[str, Any]:
    try:
        payload = fn()
        try:
            passed = bool(require(payload)) if require is not None else True
        except Exception as exc:
            checks.append({"name": name, "passed": False, "error": str(exc)})
            return payload
        checks.append({"name": name, "passed": passed, "error": ""})
        return payload
    except (OSError, TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        checks.append({"name": name, "passed": False, "error": str(exc)})
        return {}


def answers_with_one_mistake(exercises: list[dict[str, Any]]) -> list[dict[str, str]]:
    answers = []
    for index, exercise in enumerate(exercises):
        correct = str(exercise.get("correct_answer") or "")
        selected = correct
        if index == 0:
            selected = first_wrong_answer(exercise, correct)
        answers.append(
            {
                "exercise_id": str(exercise.get("exercise_id") or ""),
                "selected_answer": selected,
            },
        )
    return answers


def first_wrong_answer(exercise: dict[str, Any], correct: str) -> str:
    for option in exercise.get("options") or []:
        label = str(option.get("label") or "")
        if label and label != correct:
            return label
    return "__wrong__"


if __name__ == "__main__":
    main()
