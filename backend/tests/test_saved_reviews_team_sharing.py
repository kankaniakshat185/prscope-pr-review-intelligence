import pytest

from app.models.pr import ReviewEvent, SavedReview, SessionLocal, User
from app.services.auth import create_access_token


def _create_user_and_token(username: str):
    db = SessionLocal()
    try:
        user = User(github_id=f"gh-{username}", username=username, avatar_url="", email=f"{username}@example.com")
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    finally:
        db.close()
    return create_access_token(data={"sub": str(user_id)}), user_id


def _cleanup(user_ids=(), repositories=()):
    db = SessionLocal()
    try:
        if repositories:
            review_ids = [
                r.id for r in db.query(SavedReview).filter(SavedReview.repository.in_(repositories)).all()
            ]
            if review_ids:
                db.query(ReviewEvent).filter(ReviewEvent.review_id.in_(review_ids)).delete(synchronize_session=False)
            db.query(SavedReview).filter(SavedReview.repository.in_(repositories)).delete(synchronize_session=False)
        if user_ids:
            db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _save_review(client, token, repository, pr_number=1, **overrides):
    body = {
        "repository": repository,
        "repository_owner": repository.split("/")[0],
        "repository_name": repository.split("/")[1],
        "pr_number": pr_number,
        "pr_title": "Test PR",
        "pr_url": f"https://github.com/{repository}/pull/{pr_number}",
        "risk_score": 3.0,
        "risk_category": "Low Risk",
        "executive_summary": "Looks fine.",
        "review_status": "IN_PROGRESS",
        "review_notes": "",
        **overrides,
    }
    r = client.post(
        "/api/analysis/workspace/reviews",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def two_users(client, mock_token):
    token_b, user_id_b = _create_user_and_token("teammate-bob")
    yield mock_token, token_b, user_id_b
    _cleanup(user_ids=[user_id_b])


def test_default_list_only_returns_my_own_reviews(client, two_users):
    token_a, token_b, _ = two_users
    repository = "acme/team-sharing-default-list"
    try:
        _save_review(client, token_a, repository)
        _save_review(client, token_b, repository, pr_number=2)

        r = client.get(
            "/api/analysis/workspace/reviews",
            headers={"Authorization": f"Bearer {token_a}"},
            params={"repository": repository},
        )
        assert r.status_code == 200
        prs = {row["pr_number"] for row in r.json()}
        assert prs == {1}  # not bob's PR #2
    finally:
        _cleanup(repositories=[repository])


def test_team_view_requires_repository_param(client, mock_token):
    r = client.get(
        "/api/analysis/workspace/reviews",
        headers={"Authorization": f"Bearer {mock_token}"},
        params={"team": "true"},
    )
    assert r.status_code == 400


def test_team_view_is_forbidden_without_a_prior_review_of_that_repo(client, mock_token):
    r = client.get(
        "/api/analysis/workspace/reviews",
        headers={"Authorization": f"Bearer {mock_token}"},
        params={"team": "true", "repository": "acme/never-reviewed-by-me"},
    )
    assert r.status_code == 403


def test_team_view_shows_everyones_reviews_with_author_username(client, two_users):
    token_a, token_b, user_id_b = two_users
    repository = "acme/team-sharing-team-view"
    try:
        _save_review(client, token_a, repository, pr_number=1)
        _save_review(client, token_b, repository, pr_number=2)

        r = client.get(
            "/api/analysis/workspace/reviews",
            headers={"Authorization": f"Bearer {token_a}"},
            params={"team": "true", "repository": repository},
        )
        assert r.status_code == 200
        body = r.json()
        prs = {row["pr_number"]: row["author_username"] for row in body}
        assert prs[1] is not None  # token_a's own review, some username
        assert prs[2] == "teammate-bob"
    finally:
        _cleanup(repositories=[repository])


def test_review_detail_visible_to_teammate_who_has_reviewed_same_repo(client, two_users):
    token_a, token_b, _ = two_users
    repository = "acme/team-sharing-detail-visible"
    try:
        _save_review(client, token_a, repository, pr_number=1)
        review_b = _save_review(client, token_b, repository, pr_number=2)

        # token_a can see token_b's review because token_a has also reviewed this repo
        r = client.get(
            f"/api/analysis/workspace/reviews/{review_b['id']}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert r.status_code == 200
        assert r.json()["pr_number"] == 2

        r_events = client.get(
            f"/api/analysis/workspace/reviews/{review_b['id']}/events",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert r_events.status_code == 200
    finally:
        _cleanup(repositories=[repository])


def test_review_detail_hidden_from_a_user_with_no_reviews_in_that_repo(client, two_users):
    token_a, token_b, _ = two_users
    repository = "acme/team-sharing-detail-hidden"
    try:
        review_b = _save_review(client, token_b, repository, pr_number=1)

        # token_a has never reviewed anything in this repo - can't see it
        r = client.get(
            f"/api/analysis/workspace/reviews/{review_b['id']}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert r.status_code == 404
    finally:
        _cleanup(repositories=[repository])
