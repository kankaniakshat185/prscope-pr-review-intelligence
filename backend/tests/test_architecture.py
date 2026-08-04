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
