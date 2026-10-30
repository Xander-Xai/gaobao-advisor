"""Admin school listing, filtering, sorting and stats."""

from __future__ import annotations

from tests.conftest import auth_header, login


def _get(client, token, path, **params):
    return client.get(path, params=params, headers=auth_header(token))


class TestSchoolListing:
    def test_lists_synthetic_schools_with_aggregates(self, admin_client):
        token = login(admin_client, "viewer")
        response = _get(admin_client, token, "/api/v1/admin/schools", page=1, page_size=3)
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 8
        assert body["pages"] == 3
        assert len(body["items"]) == 3
        first = body["items"][0]
        assert first["name"].endswith("（合成）")
        assert first["score_count"] > 0
        assert first["plan_count"] >= 0
        assert first["special_type"] == "SYNTHETIC_DEMO_DATA"

    def test_filters_by_keyword_province_and_level(self, admin_client):
        token = login(admin_client, "viewer")
        keyword = _get(admin_client, token, "/api/v1/admin/schools", q="北辰")
        assert keyword.status_code == 200
        assert keyword.json()["total"] == 1
        assert "北辰" in keyword.json()["items"][0]["name"]

        province = _get(admin_client, token, "/api/v1/admin/schools", province="示例省·甲")
        assert province.status_code == 200
        assert all(item["province"] == "示例省·甲" for item in province.json()["items"])

        level = _get(admin_client, token, "/api/v1/admin/schools", level="985")
        assert level.status_code == 200
        assert all(item["level"] == "985" for item in level.json()["items"])

    def test_sorting_is_whitelisted(self, admin_client):
        token = login(admin_client, "viewer")
        response = _get(
            admin_client,
            token,
            "/api/v1/admin/schools",
            sort="name",
            order="desc",
            page_size=100,
        )
        assert response.status_code == 200
        names = [item["name"] for item in response.json()["items"]]
        assert names == sorted(names, reverse=True)

    def test_invalid_sort_and_pagination_rejected(self, admin_client):
        token = login(admin_client, "viewer")
        bad_sort = _get(admin_client, token, "/api/v1/admin/schools", sort="drop_table")
        assert bad_sort.status_code == 422
        assert bad_sort.json()["code"] == "VALIDATION_ERROR"

        bad_page = _get(admin_client, token, "/api/v1/admin/schools", page=0)
        assert bad_page.status_code == 422

        bad_range = _get(admin_client, token, "/api/v1/admin/schools", min_ranking=100, max_ranking=10)
        assert bad_range.status_code == 422
        assert "min_ranking" in bad_range.json()["message"]

    def test_filter_options_and_stats(self, admin_client):
        token = login(admin_client, "viewer")
        filters = _get(admin_client, token, "/api/v1/admin/schools/filters")
        assert filters.status_code == 200
        assert "示例省·甲" in filters.json()["provinces"]
        assert "985" in filters.json()["levels"]

        stats = _get(admin_client, token, "/api/v1/admin/stats")
        assert stats.status_code == 200
        body = stats.json()
        assert body["data_profile"] == "SYNTHETIC_DEMO"
        assert body["schools"] == 8
        assert body["admission_scores"] >= 1
        assert "jobs_by_status" in body


class TestSchoolDetail:
    def test_returns_scores_and_plans(self, admin_client):
        token = login(admin_client, "viewer")
        listing = _get(admin_client, token, "/api/v1/admin/schools", page_size=1).json()
        school_id = listing["items"][0]["id"]
        response = _get(admin_client, token, f"/api/v1/admin/schools/{school_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == school_id
        assert body["scores"]
        assert "min_score" in body["scores"][0]
        assert "plans" in body

    def test_missing_school_returns_404_code(self, admin_client):
        token = login(admin_client, "viewer")
        response = _get(admin_client, token, "/api/v1/admin/schools/999999")
        assert response.status_code == 404
        body = response.json()
        assert body["code"] == "SCHOOL_NOT_FOUND"
        assert body["request_id"]


class TestReadAuth:
    def test_anonymous_read_returns_401(self, admin_client):
        response = admin_client.get("/api/v1/admin/schools")
        assert response.status_code == 401
        assert response.json()["code"] == "ADMIN_TOKEN_INVALID"
