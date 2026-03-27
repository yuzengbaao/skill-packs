"""收割器系统全套单元测试"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# 设置环境变量（脚本在模块级别初始化 SESSION headers）
os.environ.setdefault("GH_TOKEN", "test_token_for_unit_tests")

import pytest
import requests

# 让导入路径生效
sys.path.insert(0, "/root/.openclaw/workspace/scripts")

from community_executor import (
    star_repo, check_starred, follow_user, check_following,
    fork_repo, post_comment, get_issue, extract_repos, extract_usernames,
    execute_community_bounty, scan_and_execute_community, load_state, save_state,
)
from bounty_radar import (
    categorize_bounty, parse_reward_rtc, scan_bounties,
    get_existing_queue_urls,
)
from auto_harvester import (
    harvest, get_issue_body, get_issue_comments, is_already_claimed,
    generate_code_claim, generate_generic_claim, extract_requirements,
    extract_reward,
)

# --- Fixtures ---

@pytest.fixture
def tmp_state(tmp_path, monkeypatch):
    """使用临时状态文件"""
    state_file = tmp_path / "bounty_state.json"
    monkeypatch.setattr("community_executor.STATE_FILE", state_file)
    monkeypatch.setattr("bounty_radar.STATE_FILE", state_file)
    monkeypatch.setattr("auto_harvester.load_state", lambda: {
        "claimed_issues": [],
        "starred_repos": [],
        "followed_users": [],
        "forked_repos": [],
        "last_scan": "",
    })
    return state_file


@pytest.fixture
def tmp_queue(tmp_path, monkeypatch):
    """使用临时队列文件"""
    queue_file = tmp_path / "bounty_queue.log"
    monkeypatch.setattr("auto_harvester.QUEUE_FILE", queue_file)
    return queue_file


# ============ community_executor Tests ============

class TestExtractRepos:
    def test_single_repo(self):
        text = "Check out https://github.com/rustchain-xyz/rustchain for details"
        assert extract_repos(text) == ["rustchain-xyz/rustchain"]

    def test_multiple_repos(self):
        text = "Star https://github.com/owner/repo1 and https://github.com/owner/repo2"
        repos = extract_repos(text)
        assert "owner/repo1" in repos
        assert "owner/repo2" in repos

    def test_excludes_bounty_repo(self):
        text = "See https://github.com/Scottcjn/rustchain-bounties and https://github.com/other/repo"
        assert extract_repos(text) == ["other/repo"]

    def test_no_repos(self):
        assert extract_repos("No repos here") == []

    def test_deduplication(self):
        text = "Star https://github.com/a/b and https://github.com/a/b"
        assert extract_repos(text) == ["a/b"]


class TestExtractUsernames:
    def test_single_user(self):
        text = "Follow https://github.com/Scottcjn"
        assert "Scottcjn" in extract_usernames(text)

    def test_no_usernames(self):
        assert extract_usernames("No users") == []


class TestStarRepo:
    @patch("community_executor.SESSION")
    def test_star_success_204(self, mock_session):
        mock_session.put.return_value.status_code = 204
        assert star_repo("owner", "repo") is True

    @patch("community_executor.SESSION")
    def test_star_success_200(self, mock_session):
        mock_session.put.return_value.status_code = 200
        assert star_repo("owner", "repo") is True

    @patch("community_executor.SESSION")
    def test_star_failure(self, mock_session):
        mock_session.put.return_value.status_code = 500
        assert star_repo("owner", "repo") is False


class TestCheckStarred:
    @patch("community_executor.SESSION")
    def test_already_starred(self, mock_session):
        mock_session.get.return_value.status_code = 204
        assert check_starred("owner", "repo") is True

    @patch("community_executor.SESSION")
    def test_not_starred(self, mock_session):
        mock_session.get.return_value.status_code = 404
        assert check_starred("owner", "repo") is False


class TestFollowUser:
    @patch("community_executor.SESSION")
    def test_follow_success(self, mock_session):
        mock_session.put.return_value.status_code = 204
        assert follow_user("username") is True

    @patch("community_executor.SESSION")
    def test_follow_failure(self, mock_session):
        mock_session.put.return_value.status_code = 500
        assert follow_user("username") is False


class TestPostComment:
    @patch("community_executor.SESSION")
    def test_post_success(self, mock_session):
        mock_session.post.return_value.status_code = 201
        assert post_comment("repo", 1, "test") is True

    @patch("community_executor.SESSION")
    def test_post_failure(self, mock_session):
        mock_session.post.return_value.status_code = 403
        assert post_comment("repo", 1, "test") is False


class TestExecuteCommunityBounty:
    @patch("community_executor.post_comment", return_value=True)
    @patch("community_executor.star_repo", return_value=True)
    @patch("community_executor.check_starred", return_value=False)
    @patch("community_executor.get_issue")
    def test_star_bounty_execution(self, mock_get, mock_check, mock_star, mock_post, tmp_state):
        mock_get.return_value = {
            "number": 100,
            "title": "Star our repos!",
            "body": "Please star https://github.com/rustchain-xyz/rustchain",
            "labels": [{"name": "bounty"}, {"name": "community"}],
        }
        result = execute_community_bounty(100)
        assert result.success is True
        assert any("Starred" in a for a in result.actions)
        mock_post.assert_called_once()

    @patch("community_executor.execute_community_bounty")
    @patch("community_executor.get_issue")
    def test_already_claimed_skips(self, mock_get, mock_exec, tmp_state):
        tmp_state.write_text(json.dumps({"claimed_issues": [100], "starred_repos": [], "followed_users": [], "forked_repos": [], "last_scan": ""}))
        result = execute_community_bounty(100)
        assert result.success is False
        mock_get.assert_not_called()

    @patch("community_executor.post_comment", return_value=True)
    @patch("community_executor.follow_user", return_value=True)
    @patch("community_executor.get_issue")
    def test_follow_bounty_execution(self, mock_get, mock_follow, mock_post, tmp_state):
        mock_get.return_value = {
            "number": 101,
            "title": "Follow us",
            "body": "Follow https://github.com/Scottcjn",
            "labels": [{"name": "bounty"}, {"name": "community"}],
        }
        result = execute_community_bounty(101)
        assert result.success is True
        mock_follow.assert_called_once()


# ============ bounty_radar Tests ============

class TestCategorizeBounty:
    def test_community(self):
        labels = [{"name": "bounty"}, {"name": "community"}]
        assert categorize_bounty(labels) == "community"

    def test_code(self):
        labels = [{"name": "bounty"}, {"name": "code"}]
        assert categorize_bounty(labels) == "code"

    def test_content(self):
        labels = [{"name": "bounty"}, {"name": "content"}]
        assert categorize_bounty(labels) == "content"

    def test_gaming(self):
        labels = [{"name": "bounty"}, {"name": "gaming"}]
        assert categorize_bounty(labels) == "gaming"

    def test_other(self):
        labels = [{"name": "bounty"}, {"name": "easy"}]
        assert categorize_bounty(labels) == "other"

    def test_propagation(self):
        labels = [{"name": "bounty"}, {"name": "propagation"}]
        assert categorize_bounty(labels) == "community"


class TestParseRewardRtc:
    def test_single_value(self):
        assert parse_reward_rtc([{"name": "25-rtc"}]) == 25

    def test_range(self):
        assert parse_reward_rtc([{"name": "1-4-rtc"}]) == 4

    def test_high_value(self):
        assert parse_reward_rtc([{"name": "200-rtc"}]) == 200

    def test_no_rtc(self):
        assert parse_reward_rtc([{"name": "bounty"}, {"name": "easy"}]) == 0

    def test_zero_rtc(self):
        assert parse_reward_rtc([{"name": "0-rtc"}]) == 0


# ============ auto_harvester Tests ============

class TestIsAlreadyClaimed:
    def test_not_claimed(self):
        comments = [{"user": {"login": "other"}, "body": "Looks interesting"}]
        assert is_already_claimed(comments) is False

    def test_claimed_by_other(self):
        comments = [{"user": {"login": "someone"}, "body": "I would like to work on this"}]
        assert is_already_claimed(comments) is True

    def test_claimed_by_self_not_counted(self):
        comments = [{"user": {"login": "yuzengbaao"}, "body": "I would like to work on this"}]
        assert is_already_claimed(comments) is False


class TestExtractRequirements:
    def test_basic_requirements(self):
        body = "## Bounty\n\n### Requirements\n- Implement feature A\n- Add tests\n- Update docs\n\n### Bonus\n"
        reqs = extract_requirements(body)
        assert len(reqs) == 3
        assert "Implement feature A" in reqs

    def test_numbered_requirements(self):
        body = "### Requirements:\n1. First thing\n2. Second thing\n"
        reqs = extract_requirements(body)
        assert len(reqs) == 2
        assert reqs[0] == "First thing"

    def test_no_requirements(self):
        body = "Just some text"
        assert extract_requirements(body) == []


class TestExtractReward:
    def test_from_title(self):
        assert extract_reward("Some task (50 RTC)", "") == "50 RTC"

    def test_from_body(self):
        assert extract_reward("Task", "Reward: 100 RTC for completion") == "100 RTC"

    def test_with_commas(self):
        assert extract_reward("N64 Mining ROM (5,000 RTC Program)", "") == "5000 RTC"

    def test_no_reward(self):
        assert extract_reward("Task", "No reward here") == "Unknown"


class TestGenerateCodeClaim:
    def test_contains_wallet(self):
        claim = generate_code_claim(1, "Test", "Requirements:\n- Do thing", ["bounty", "code"])
        assert "RTC0816b68b604630945c94cde35da4641a926aa4fd" in claim

    def test_contains_issue_reference(self):
        claim = generate_code_claim(42, "Build SDK", "Build a Python SDK", ["bounty", "code"])
        assert "#42" in claim
        assert "Build SDK" in claim

    def test_sdk_approach(self):
        claim = generate_code_claim(1, "Create SDK", "Build SDK for RustChain", ["bounty", "code"])
        assert "SDK" in claim or "sdk" in claim

    def test_no_template_language(self):
        claim = generate_code_claim(1, "Test", "Requirements:\n- Do thing", ["bounty", "code"])
        assert "Cryptographic logic" not in claim
        assert "zeroed in memory" not in claim


class TestGenerateGenericClaim:
    def test_contains_wallet(self):
        claim = generate_generic_claim(1, "Test", "body")
        assert "RTC0816b68b604630945c94cde35da4641a926aa4fd" in claim

    def test_contains_i_would_like(self):
        claim = generate_generic_claim(1, "Test", "body")
        assert "I would like to work on this" in claim


class TestHarvestDedup:
    @patch("auto_harvester.time.sleep")
    @patch("auto_harvester.post_comment", return_value=True)
    @patch("auto_harvester.get_issue_comments", return_value=[])
    @patch("auto_harvester.get_issue_body")
    @patch("auto_harvester.execute_community_bounty", return_value=MagicMock(success=True, actions=["Starred repo"]))
    def test_no_reprocess_already_claimed(self, mock_exec, mock_get_body, mock_get_comments, mock_post, mock_sleep, tmp_queue, tmp_state, monkeypatch):
        """已处理的 issue 不应再次处理"""
        monkeypatch.setattr("auto_harvester.load_state", lambda: {
            "claimed_issues": [200], "starred_repos": [], "followed_users": [], "forked_repos": [], "last_scan": ""
        })
        tmp_queue.write_text("[2026-01-01 00:00:00] BOUNTY FOUND | Test (10 RTC) | https://github.com/Scottcjn/rustchain-bounties/issues/200\n")
        mock_get_body.return_value = {
            "number": 200, "title": "Test", "body": "body",
            "labels": [{"name": "bounty"}, {"name": "community"}],
        }

        harvest()

        # Issue 200 已在 state 中，不应调用任何 API
        mock_get_body.assert_not_called()
        mock_exec.assert_not_called()
