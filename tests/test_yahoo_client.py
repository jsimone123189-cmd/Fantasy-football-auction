from draft_helper.yahoo_client import YahooFantasyClient


class FakeOAuth:
    def get_valid_access_token(self):
        return "fake-token"


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code
        self.text = str(json_data)

    def json(self):
        return self._json


def make_client(monkeypatch, response_json):
    client = YahooFantasyClient(FakeOAuth())
    monkeypatch.setattr(client.session, "get", lambda *a, **k: FakeResponse(response_json))
    return client


def test_get_user_leagues(monkeypatch):
    data = {
        "fantasy_content": {
            "users": {
                "0": {
                    "user": [
                        [{"guid": "USERGUID"}],
                        {
                            "games": {
                                "0": {
                                    "game": [
                                        [{"game_key": "423"}, {"code": "nfl"}, {"season": "2023"}],
                                        {
                                            "leagues": {
                                                "0": {
                                                    "league": [
                                                        [
                                                            {"league_key": "423.l.12345"},
                                                            {"league_id": "12345"},
                                                            {"name": "The League"},
                                                            {"draft_status": "postdraft"},
                                                        ]
                                                    ]
                                                },
                                                "count": 1,
                                            }
                                        },
                                    ]
                                },
                                "count": 1,
                            }
                        },
                    ]
                },
                "count": 1,
            }
        }
    }
    client = make_client(monkeypatch, data)
    leagues = client.get_user_leagues()
    assert len(leagues) == 1
    assert leagues[0]["league_key"] == "423.l.12345"
    assert leagues[0]["league_id"] == "12345"
    assert leagues[0]["season"] == "2023"


def test_get_league_teams(monkeypatch):
    data = {
        "fantasy_content": {
            "league": [
                [{"league_key": "423.l.12345"}],
                {
                    "teams": {
                        "0": {
                            "team": [
                                [
                                    {"team_key": "423.l.12345.t.1"},
                                    {"team_id": "1"},
                                    {"name": "Team Rocket"},
                                    {
                                        "managers": [
                                            {"manager": {"manager_id": "1", "nickname": "Jess", "guid": "GUID1"}}
                                        ]
                                    },
                                ]
                            ]
                        },
                        "count": 1,
                    }
                },
            ]
        }
    }
    client = make_client(monkeypatch, data)
    teams = client.get_league_teams("423.l.12345")
    assert teams == [
        {
            "team_key": "423.l.12345.t.1",
            "team_id": "1",
            "team_name": "Team Rocket",
            "manager_name": "Jess",
            "manager_guid": "GUID1",
        }
    ]


def test_get_draft_results(monkeypatch):
    data = {
        "fantasy_content": {
            "league": [
                [{"league_key": "423.l.12345"}],
                {
                    "draft_results": {
                        "0": {
                            "draft_result": {
                                "pick": 1,
                                "round": 1,
                                "team_key": "423.l.12345.t.1",
                                "player_key": "423.p.100",
                                "cost": "45",
                            }
                        },
                        "count": 1,
                    }
                },
            ]
        }
    }
    client = make_client(monkeypatch, data)
    picks = client.get_draft_results("423.l.12345")
    assert len(picks) == 1
    assert picks[0]["cost"] == "45"
    assert picks[0]["player_key"] == "423.p.100"


def test_get_players_by_keys(monkeypatch):
    data = {
        "fantasy_content": {
            "league": [
                [{"league_key": "423.l.12345"}],
                {
                    "players": {
                        "0": {
                            "player": [
                                [
                                    {"player_key": "423.p.100"},
                                    {"player_id": "100"},
                                    {"name": {"full": "Christian McCaffrey"}},
                                    {"editorial_team_abbr": "SF"},
                                    {"display_position": "RB"},
                                ]
                            ]
                        },
                        "count": 1,
                    }
                },
            ]
        }
    }
    client = make_client(monkeypatch, data)
    players = client.get_players_by_keys("423.l.12345", ["423.p.100"])
    assert players["423.p.100"] == {
        "player_name": "Christian McCaffrey",
        "position": "RB",
        "nfl_team": "SF",
    }
