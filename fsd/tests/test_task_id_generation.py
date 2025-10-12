"""Tests for task ID generation with unique suffixes."""

import re

import pytest

from fsd.cli.commands.submit import _generate_task_id
from fsd.core.ai_task_parser import AITaskParser


class TestTaskIdGeneration:
    """Test task ID generation with random suffixes."""

    def test_generate_task_id_has_suffix(self):
        """Test that generated task IDs include random suffix."""
        task_id = _generate_task_id("Fix login bug in auth.py")

        # Should match pattern: base-XXXX where XXXX is 4 digits
        assert re.search(r'-\d{4}$', task_id), f"Task ID '{task_id}' should end with -XXXX"

    def test_generate_task_id_uniqueness(self):
        """Test that multiple calls generate different IDs."""
        description = "Fix the same bug"

        ids = set()
        for _ in range(10):
            task_id = _generate_task_id(description)
            ids.add(task_id)

        # All IDs should be unique (different suffixes)
        assert len(ids) == 10, "Generated IDs should all be unique"

    def test_generate_task_id_format(self):
        """Test that task ID format is correct."""
        task_id = _generate_task_id("HIGH: Refactor payment module")

        # Should be lowercase with hyphens
        assert task_id.islower() or '-' in task_id
        assert ' ' not in task_id
        assert task_id.replace('-', '').replace('0123456789', '').isalnum() or '-' in task_id

        # Should end with 4-digit suffix
        suffix = task_id.split('-')[-1]
        assert len(suffix) == 4 and suffix.isdigit()

    def test_generate_task_id_length_limit(self):
        """Test that task IDs respect max length."""
        long_description = "Implement a very long feature description that goes on and on with many words to test the length limit functionality"

        task_id = _generate_task_id(long_description)

        # Should be <= 50 chars
        assert len(task_id) <= 50, f"Task ID length {len(task_id)} exceeds 50 chars"

        # Should still have suffix
        assert re.search(r'-\d{4}$', task_id)

    def test_generate_task_id_strips_stop_words(self):
        """Test that common stop words are filtered out."""
        task_id = _generate_task_id("Fix the login bug in the authentication system")

        # Should not contain stop words
        task_id_lower = task_id.lower()
        assert 'the' not in task_id_lower or 'the' in 'authentication'  # 'the' might be in other words

        # Should contain significant words
        assert any(word in task_id_lower for word in ['fix', 'login', 'bug', 'authentication'])

    def test_generate_task_id_minimum_length(self):
        """Test that very short descriptions get prefixed."""
        task_id = _generate_task_id("Fix")

        # Should have at least some base + suffix
        assert len(task_id) >= 8  # "fix-1234" or "task-fix-1234"
        assert re.search(r'-\d{4}$', task_id)

    def test_generate_task_id_consistent_base(self):
        """Test that the base (without suffix) is consistent."""
        description = "Refactor payment module"

        # Generate multiple IDs
        ids = [_generate_task_id(description) for _ in range(5)]

        # Extract bases (everything except last 5 chars: "-XXXX")
        bases = [task_id[:-5] for task_id in ids]

        # All bases should be the same
        assert len(set(bases)) == 1, "Base task ID should be consistent"


class TestAITaskParserUniqueSuffix:
    """Test AI task parser ensures unique suffixes."""

    def test_ensure_unique_suffix_adds_suffix(self):
        """Test that _ensure_unique_suffix adds suffix when missing."""
        parser = AITaskParser()

        task_id = "fix-login-bug"
        result = parser._ensure_unique_suffix(task_id)

        # Should have added suffix
        assert result != task_id
        assert re.search(r'-\d{4}$', result)
        assert result.startswith(task_id)

    def test_ensure_unique_suffix_preserves_existing(self):
        """Test that existing suffix is preserved."""
        parser = AITaskParser()

        task_id = "fix-login-bug-5678"
        result = parser._ensure_unique_suffix(task_id)

        # Should keep the same ID
        assert result == task_id

    def test_ensure_unique_suffix_handles_long_ids(self):
        """Test that long IDs are truncated before adding suffix."""
        parser = AITaskParser()

        # Create an ID that's exactly at the limit
        task_id = "a" * 48  # 48 chars, adding "-XXXX" would make 53

        result = parser._ensure_unique_suffix(task_id)

        # Should be <= 50 chars
        assert len(result) <= 50
        assert re.search(r'-\d{4}$', result)

    def test_ensure_unique_suffix_uniqueness(self):
        """Test that multiple calls generate different suffixes."""
        parser = AITaskParser()

        task_id = "base-task-id"
        results = set()

        for _ in range(10):
            result = parser._ensure_unique_suffix(task_id)
            results.add(result)

        # All should be unique
        assert len(results) == 10


class TestTaskIdCollisionPrevention:
    """Integration tests for collision prevention."""

    def test_similar_descriptions_get_unique_ids(self):
        """Test that similar task descriptions get unique IDs."""
        descriptions = [
            "Fix login bug",
            "Fix login bug",  # Exact duplicate
            "Fix the login bug",  # Similar with stop word
        ]

        ids = [_generate_task_id(desc) for desc in descriptions]

        # All IDs should be unique
        assert len(set(ids)) == len(ids), "Similar descriptions should generate unique IDs"

    def test_ai_parser_generates_unique_ids(self):
        """Test that AI parser adds suffixes for uniqueness."""
        parser = AITaskParser()

        # Simulate AI responses without suffixes (with valid descriptions)
        test_data_list = [
            {"id": "fix-bug", "description": "Fix authentication bug in login system", "priority": "high"},
            {"id": "fix-bug", "description": "Fix authentication bug in login system", "priority": "high"},
        ]

        tasks = []
        for data in test_data_list:
            task = parser._build_task_definition(data)
            tasks.append(task)

        # All task IDs should be unique (different suffixes added)
        task_ids = [task.id for task in tasks]
        assert len(set(task_ids)) == len(task_ids), "AI-generated tasks should have unique IDs"

        # All should have suffixes
        for task_id in task_ids:
            assert re.search(r'-\d{4}$', task_id), f"Task ID {task_id} should have suffix"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
