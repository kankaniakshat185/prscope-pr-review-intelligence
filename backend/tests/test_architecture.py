from app.services.architecture import validate_architecture

# Regression test for a real bug: this module used to split patches on the
# literal two-character string '\\n' instead of an actual newline, which
# meant added_lines was always effectively empty and no violation could ever
# be detected. If this test starts failing, that bug is back.


def test_detects_restricted_import_in_added_lines():
    pr_data = {
        "files": [
            {
                "filename": "auth/login.py",
                "patch": "@@ -1,3 +1,4 @@\n import os\n+from payment import charge_card\n def login():\n     pass",
            }
        ]
    }
    violations = validate_architecture(pr_data)
    assert len(violations) == 1
    assert violations[0]["rule"] == "auth cannot import payment"


def test_clean_pr_has_no_violations():
    pr_data = {
        "files": [
            {
                "filename": "auth/login.py",
                "patch": "@@ -1,3 +1,4 @@\n import os\n+import logging\n def login():\n     pass",
            }
        ]
    }
    assert validate_architecture(pr_data) == []


def test_custom_rules_yaml_is_respected():
    custom_rules = "billing:\n  cannot_import:\n    - frontend\n"
    pr_data = {
        "files": [
            {
                "filename": "billing/invoice.py",
                "patch": "@@ -1,2 +1,3 @@\n import os\n+from frontend import widgets\n pass",
            }
        ]
    }
    violations = validate_architecture(pr_data, custom_rules)
    assert len(violations) == 1
    assert violations[0]["rule"] == "billing cannot import frontend"


def test_python_files_use_ast_detection_and_ignore_string_literal_mentions():
    # Regex, matching purely on line text, would have flagged the line
    # "import payment example usage" below since it starts with "import" and
    # contains "payment" - even though it's just the contents of a triple-
    # quoted string, not a real import statement. AST-based detection knows
    # the difference.
    pr_data = {
        "files": [
            {
                "filename": "auth/login.py",
                "patch": (
                    "@@ -1,2 +1,5 @@\n"
                    " import os\n"
                    "+DOCS = \"\"\"\n"
                    "+import payment example usage\n"
                    "+\"\"\"\n"
                ),
            }
        ]
    }
    assert validate_architecture(pr_data) == []


def test_falls_back_to_regex_when_python_fragment_does_not_parse():
    # This reconstructed fragment is not valid Python on its own (unclosed
    # paren), so AST parsing fails - the module should still catch the
    # restricted import via the regex fallback rather than silently missing it.
    pr_data = {
        "files": [
            {
                "filename": "auth/login.py",
                "patch": "@@ -1,2 +1,3 @@\n def foo(\n+    import payment\n",
            }
        ]
    }
    violations = validate_architecture(pr_data)
    assert len(violations) == 1
    assert violations[0]["rule"] == "auth cannot import payment"


def test_non_python_files_still_use_regex_detection():
    pr_data = {
        "files": [
            {
                "filename": "frontend/db.ts",
                "patch": "@@ -1,2 +1,3 @@\n import React from 'react'\n+import db from 'database'\n",
            }
        ]
    }
    violations = validate_architecture(pr_data)
    assert len(violations) == 1
    assert violations[0]["rule"] == "frontend cannot import database"
