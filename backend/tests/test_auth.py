import uuid

import jwt

from sovereign.auth import hash_password, issue_token, read_token, verify_password
from sovereign.config import Settings


def test_password_round_trip():
    stored = hash_password("correct horse")
    assert verify_password("correct horse", stored)
    assert not verify_password("wrong", stored)
    assert not verify_password("anything", None)


SECRET_A = "a" * 40
SECRET_B = "b" * 40


def test_token_round_trip_and_tampering():
    settings = Settings(jwt_secret=SECRET_A)
    user_id = uuid.uuid4()
    token = issue_token(user_id, settings)
    assert read_token(token, settings) == user_id
    assert read_token(token, Settings(jwt_secret=SECRET_B)) is None
    assert read_token(token + "x", settings) is None


def test_expired_and_unsigned_tokens_are_rejected():
    settings = Settings(jwt_secret=SECRET_A, session_hours=-1)
    assert read_token(issue_token(uuid.uuid4(), settings), settings) is None
    unsigned = jwt.encode({"sub": str(uuid.uuid4()), "exp": 9999999999}, key=None, algorithm="none")
    assert read_token(unsigned, settings) is None
