"""从 SKILL.md 提取的测试用例 + 真实数据验证"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from bounty_parser import BountyInfo, _parse_reward_from_labels
from unittest.mock import patch, MagicMock
import pytest


class TestParseRewardFromLabels:
    """奖励标签解析测试"""

    def test_single_rtc_label(self):
        assert _parse_reward_from_labels([{"name": "5-rtc"}]) == 5

    def test_rtc_25(self):
        assert _parse_reward_from_labels([{"name": "25-rtc"}]) == 25

    def test_range_rtc_label(self):
        assert _parse_reward_from_labels([{"name": "1-4-rtc"}]) == 4

    def test_range_1_10(self):
        assert _parse_reward_from_labels([{"name": "1-10-rtc"}]) == 10

    def test_high_value(self):
        assert _parse_reward_from_labels([{"name": "200-rtc"}]) == 200

    def test_no_rtc_label(self):
        assert _parse_reward_from_labels([{"name": "bounty"}, {"name": "easy"}]) == 0

    def test_mixed_labels(self):
        assert _parse_reward_from_labels([
            {"name": "bounty"}, {"name": "50-rtc"}, {"name": "code"}
        ]) == 50

    def test_zero_rtc(self):
        assert _parse_reward_from_labels([{"name": "0-rtc"}]) == 0

    def test_real_issue_2322(self):
        """真实 issue #2322: Retro Screenshot Gallery — 1-4-rtc"""
        labels = [{"name": "bounty"}, {"name": "community"}, {"name": "gaming"}, {"name": "1-4-rtc"}]
        assert _parse_reward_from_labels(labels) == 4

    def test_real_issue_2320(self):
        """真实 issue #2320: Cabinet Hunt — 1-10-rtc"""
        labels = [{"name": "bounty"}, {"name": "gaming"}, {"name": "cabinet-hunt"}, {"name": "1-10-rtc"}]
        assert _parse_reward_from_labels(labels) == 10

    def test_real_issue_2451(self):
        """真实 issue #2451: 无 RTC 标签"""
        labels = [{"name": "bounty"}, {"name": "community"}, {"name": "mining"}]
        assert _parse_reward_from_labels(labels) == 0


class TestBountyInfo:
    """BountyInfo 数据类测试"""

    def test_creation_defaults(self):
        b = BountyInfo(issue_number=1, title="Test", reward_rtc=5)
        assert b.labels == []
        assert b.url == ""
        assert b.status == "open"

    def test_creation_with_values(self):
        b = BountyInfo(
            issue_number=42,
            title="Build SDK",
            reward_rtc=100,
            labels=["code", "rust"],
            url="https://github.com/test/repo/issues/42",
        )
        assert b.issue_number == 42
        assert b.reward_rtc == 100
        assert len(b.labels) == 2


class TestGitHubAPI:
    """GitHubAPI 类测试（mock）"""

    @patch('requests.Session')
    def test_init_sets_headers(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.headers = {}
        mock_session_cls.return_value = mock_session
        from github_api import GitHubAPI
        api = GitHubAPI("fake_token")
        assert api.session.headers["Authorization"] == "Bearer fake_token"
        assert "application/vnd.github+json" in api.session.headers["Accept"]

    @patch('requests.Session')
    def test_base_url(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.headers = {}
        mock_session_cls.return_value = mock_session
        from github_api import GitHubAPI
        api = GitHubAPI("fake_token")
        assert api.base_url == "https://api.github.com"


class TestCommunityBot:
    """社区 bot 函数测试"""

    @patch('requests.put')
    def test_star_repo_success(self, mock_put):
        from community_bot import star_repo
        mock_put.return_value.status_code = 204
        assert star_repo("owner", "repo", "token") is True

    @patch('requests.put')
    def test_star_repo_already_starred(self, mock_put):
        from community_bot import star_repo
        mock_put.return_value.status_code = 200
        assert star_repo("owner", "repo", "token") is True

    @patch('requests.put')
    def test_star_repo_failure(self, mock_put):
        from community_bot import star_repo
        mock_put.return_value.status_code = 500
        assert star_repo("owner", "repo", "token") is False

    @patch('requests.get')
    def test_check_starred_true(self, mock_get):
        from community_bot import check_starred
        mock_get.return_value.status_code = 204
        assert check_starred("owner", "repo", "token") is True

    @patch('requests.get')
    def test_check_starred_false(self, mock_get):
        from community_bot import check_starred
        mock_get.return_value.status_code = 404
        assert check_starred("owner", "repo", "token") is False

    @patch('requests.put')
    def test_follow_user_success(self, mock_put):
        from community_bot import follow_user
        mock_put.return_value.status_code = 204
        assert follow_user("username", "token") is True

    @patch('requests.get')
    def test_check_following_true(self, mock_get):
        from community_bot import check_following
        mock_get.return_value.status_code = 204
        assert check_following("username", "token") is True
