from devwatcher.sanitizer import sanitize, sanitize_dict


def test_redacts_anthropic_key():
    text = "key = sk-ant-api03-abcdefghijklmnopqrst1234567890"
    result = sanitize(text)
    assert "[REDACTED]" in result
    assert "sk-ant-api03-abcdefghijklmnopqrst1234567890" not in result


def test_redacts_openai_key():
    result = sanitize("OPENAI_KEY=sk-abcdefghijklmnopqrstuvwxyz123456")
    assert "[REDACTED]" in result


def test_redacts_jwt_token():
    token = (
        "eyJhbGciOiJIUzI1NiJ9"
        ".eyJzdWIiOiJ1c2VyIn0"
        ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    assert "[REDACTED]" in sanitize(token)


def test_redacts_aws_access_key():
    assert "[REDACTED]" in sanitize("AKIAIOSFODNN7EXAMPLE")


def test_redacts_github_token():
    assert "[REDACTED]" in sanitize("ghp_abcdefghijklmnopqrstuvwxyz1234567890AB")


def test_redacts_connection_string_password():
    url = "postgresql://admin:supersecret@localhost:5432/mydb"
    result = sanitize(url)
    assert "supersecret" not in result
    assert "[REDACTED]" in result


def test_redacts_bearer_token():
    header = "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6InRlc3QifQ"
    assert "[REDACTED]" in sanitize(header)


def test_leaves_clean_commit_message_unchanged():
    clean = "feat: add user authentication module"
    assert sanitize(clean) == clean


def test_sanitize_dict_recurses_into_values():
    d = {
        "message": "feat: add auth",
        "token": "sk-ant-api03-abcdefghijklmnopqrst1234567890",
    }
    result = sanitize_dict(d)
    assert result["message"] == "feat: add auth"
    assert "[REDACTED]" in result["token"]


def test_sanitize_dict_handles_list_values():
    d = {"files": ["main.py", "AKIAIOSFODNN7EXAMPLE", "utils.py"]}
    result = sanitize_dict(d)
    assert result["files"][0] == "main.py"
    assert "[REDACTED]" in result["files"][1]
    assert result["files"][2] == "utils.py"


def test_redacts_openai_project_key():
    result = sanitize("sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ01234567890abcde")
    assert "[REDACTED]" in result


def test_redacts_aws_sts_key():
    assert "[REDACTED]" in sanitize("ASIAIOSFODNN7EXAMPLE")


def test_redacts_aws_role_key():
    assert "[REDACTED]" in sanitize("AROAI234567890EXAMPLE")


def test_redacts_aws_bia_key():
    assert "[REDACTED]" in sanitize("ABIAIOSFODNN7EXAMPLE")


def test_redacts_aws_cca_key():
    assert "[REDACTED]" in sanitize("ACCAIOSFODNN7EXAMPLE")


def test_connection_string_preserves_scheme():
    url = "postgresql://admin:supersecret@localhost:5432/mydb"
    result = sanitize(url)
    assert "supersecret" not in result
    assert "postgresql://" in result
    assert "localhost" in result


def test_does_not_corrupt_function_call_assignment():
    code = "token = get_token()"
    assert sanitize(code) == code


def test_redacts_quoted_password_assignment():
    assert "[REDACTED]" in sanitize('password = "mysecretpassword123"')


def test_redacts_single_quoted_password():
    assert "[REDACTED]" in sanitize("password = 'mysecretpassword123'")


def test_sanitize_dict_recurses_into_nested_list():
    d = {"nested": [["main.py", "AKIAIOSFODNN7EXAMPLE"]]}
    result = sanitize_dict(d)
    assert "[REDACTED]" in result["nested"][0][1]


def test_github_app_token_gha_prefix():
    assert "[REDACTED]" in sanitize("gha_1234567890abcdefghijklmnopqrstuvwxyzABCD")
