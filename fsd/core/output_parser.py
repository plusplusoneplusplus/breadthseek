"""Parse Claude CLI output and extract structured data.

This module provides utilities to extract JSON and other structured
content from Claude Code CLI output, which may include explanations,
code blocks, and other unstructured text.
"""

import json
import re
from typing import Any, Dict, List, Optional

from .exceptions import ClaudeOutputParseError


class OutputParser:
    """Parse Claude CLI output and extract structured content."""

    @staticmethod
    def extract_json(output: str, strict: bool = True) -> Dict[str, Any]:
        """Extract JSON object from Claude output.

        Claude often wraps JSON in markdown code blocks or includes
        explanations before/after the JSON. This method extracts the
        JSON content regardless of surrounding text.

        Args:
            output: Raw output from Claude CLI
            strict: If True, raise error if no JSON found.
                   If False, return empty dict if no JSON found.

        Returns:
            Parsed JSON as dictionary

        Raises:
            ClaudeOutputParseError: If JSON cannot be found or parsed (when strict=True)
        """
        if not output or not output.strip():
            if strict:
                raise ClaudeOutputParseError("Output is empty")
            return {}

        # Try to find JSON in various formats
        json_content = None

        # 1. Try to find JSON in code blocks
        # Match: ```json\n{...}\n``` or ```\n{...}\n```
        code_block_pattern = r"```(?:json)?\s*\n([\s\S]*?)\n```"
        matches = re.findall(code_block_pattern, output, re.MULTILINE)

        for match in matches:
            # Try to parse as JSON
            try:
                json_content = json.loads(match.strip())
                break  # Found valid JSON
            except json.JSONDecodeError:
                continue

        # 2. If not found in code blocks, try to find raw JSON
        if json_content is None:
            # Look for {...} or [...] at top level
            # Find the first { and last } or first [ and last ]
            obj_start = output.find("{")
            obj_end = output.rfind("}")
            arr_start = output.find("[")
            arr_end = output.rfind("]")

            # Prefer objects over arrays
            if obj_start != -1 and obj_end != -1:
                try:
                    potential_json = output[obj_start : obj_end + 1]
                    json_content = json.loads(potential_json)
                except json.JSONDecodeError:
                    pass

            # Try array if object didn't work
            if json_content is None and arr_start != -1 and arr_end != -1:
                try:
                    potential_json = output[arr_start : arr_end + 1]
                    json_content = json.loads(potential_json)
                except json.JSONDecodeError:
                    pass

        # 3. If still not found, try line-by-line search for standalone JSON
        if json_content is None:
            lines = output.split("\n")
            json_lines = []
            in_json = False

            for line in lines:
                stripped = line.strip()
                if stripped.startswith("{") or stripped.startswith("["):
                    in_json = True
                    json_lines = [line]
                elif in_json:
                    json_lines.append(line)
                    if stripped.endswith("}") or stripped.endswith("]"):
                        # Try to parse accumulated lines
                        try:
                            json_content = json.loads("\n".join(json_lines))
                            break
                        except json.JSONDecodeError:
                            in_json = False
                            json_lines = []

        if json_content is None:
            if strict:
                raise ClaudeOutputParseError(
                    f"No valid JSON found in output. Output preview: {output[:200]}..."
                )
            return {}

        return json_content

    @staticmethod
    def extract_json_list(output: str, strict: bool = True) -> List[Dict[str, Any]]:
        """Extract list of JSON objects from output.

        Args:
            output: Raw output from Claude CLI
            strict: If True, raise error if no JSON found

        Returns:
            List of JSON objects

        Raises:
            ClaudeOutputParseError: If JSON cannot be found or parsed
        """
        result = OutputParser.extract_json(output, strict=strict)

        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            # If single object, wrap in list
            return [result]
        else:
            if strict:
                raise ClaudeOutputParseError(
                    f"Expected JSON list or object, got {type(result)}"
                )
            return []

    @staticmethod
    def extract_code_blocks(output: str, language: Optional[str] = None) -> List[str]:
        """Extract code blocks from output.

        Args:
            output: Raw output from Claude CLI
            language: Optional language filter (e.g., 'python', 'javascript')

        Returns:
            List of code block contents
        """
        if language:
            # Match specific language: ```python\ncode\n```
            pattern = rf"```{re.escape(language)}\s*\n([\s\S]*?)\n```"
        else:
            # Match any code block: ```lang\ncode\n``` or ```\ncode\n```
            pattern = r"```(?:\w+)?\s*\n([\s\S]*?)\n```"

        matches = re.findall(pattern, output, re.MULTILINE)
        return [match.strip() for match in matches]

    @staticmethod
    def extract_sections(output: str) -> Dict[str, str]:
        """Extract markdown sections from output.

        Parses output into sections based on markdown headers (##).

        Args:
            output: Raw output from Claude CLI

        Returns:
            Dictionary mapping section names to content
        """
        sections = {}
        current_section = "preamble"
        current_content = []

        for line in output.split("\n"):
            # Check for section header (## Section Name)
            if line.startswith("##"):
                # Save previous section
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()

                # Start new section
                current_section = line[2:].strip().lower().replace(" ", "_")
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

    @staticmethod
    def find_validation_result(output: str) -> bool:
        """Determine if validation passed based on output.

        Looks for common validation indicators in the output.

        Args:
            output: Raw output from Claude CLI

        Returns:
            True if validation appears to have passed, False otherwise
        """
        output_lower = output.lower()

        # Positive indicators
        positive_patterns = [
            r"validation[_\s]passed",
            r"all\s+tests?\s+pass",
            r"validation:\s*true",
            r'"validation_passed"\s*:\s*true',
            r"outcome.*success",
            r"recommendation.*complete",
        ]

        for pattern in positive_patterns:
            if re.search(pattern, output_lower):
                return True

        # Negative indicators
        negative_patterns = [
            r"validation[_\s]failed",
            r"tests?\s+failed",
            r"validation:\s*false",
            r'"validation_passed"\s*:\s*false',
            r"outcome.*failed",
            r"recommendation.*retry",
        ]

        for pattern in negative_patterns:
            if re.search(pattern, output_lower):
                return False

        # If no clear indicators, try to parse JSON
        try:
            result = OutputParser.extract_json(output, strict=False)
            if "validation_passed" in result:
                return bool(result["validation_passed"])
            if "passed" in result:
                return bool(result["passed"])
        except ClaudeOutputParseError:
            pass

        # Default to False if unclear
        return False

    @staticmethod
    def sanitize_output(output: str, max_length: int = 10000) -> str:
        """Sanitize output for logging/display.

        Args:
            output: Raw output
            max_length: Maximum length to return

        Returns:
            Sanitized output string
        """
        if not output:
            return ""

        # Remove ANSI color codes
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        cleaned = ansi_escape.sub("", output)

        # Truncate if too long
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length] + f"\n... (truncated {len(cleaned) - max_length} characters)"

        return cleaned.strip()
