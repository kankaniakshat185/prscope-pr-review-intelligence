from app.services.symbols_analysis import analyze_symbols


def test_detects_added_function():
    pr_data = {
        "files": [
            {
                "filename": "app/utils.py",
                "patch": "@@ -1,2 +1,5 @@\n import os\n+def new_helper():\n+    pass\n",
            }
        ]
    }
    result = analyze_symbols(pr_data)
    assert "new_helper" in result["functions_added"]


def test_detects_removed_function():
    pr_data = {
        "files": [
            {
                "filename": "app/utils.py",
                "patch": "@@ -1,3 +1,1 @@\n import os\n-def old_helper():\n-    pass\n",
            }
        ]
    }
    result = analyze_symbols(pr_data)
    assert "old_helper" in result["functions_removed"]


def test_no_patch_does_not_crash():
    pr_data = {"files": [{"filename": "app/binary.png", "patch": ""}]}
    result = analyze_symbols(pr_data)
    assert result == {
        "functions_modified": [],
        "functions_added": [],
        "functions_removed": [],
        "classes_modified": [],
    }
