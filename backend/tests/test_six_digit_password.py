import pytest
from pydantic import ValidationError

from app.core.security import hash_password, verify_password
from app.schemas.auth import TokenRequest, PasswordChange


def test_six_digit_password_preserves_leading_zero():
    password = "012345"
    assert TokenRequest(token="x" * 30, password=password).password == password
    assert verify_password(password, hash_password(password))
    assert not verify_password("12345", hash_password(password))


@pytest.mark.parametrize("password", ["12345", "1234567", "", "Ab1!x"])
def test_new_password_requires_exactly_six_characters(password):
    with pytest.raises(ValidationError):
        TokenRequest(token="x" * 30, password=password)
    with pytest.raises(ValidationError):
        PasswordChange(current_password="existing-password", new_password=password)


def test_existing_long_password_still_verifies():
    password = "Existing-password-42"
    assert verify_password(password, hash_password(password))


@pytest.mark.parametrize("password", ["Ab1!x?", "abcdef", "123456"])
def test_six_characters_accept_letters_numbers_and_symbols(password):
    assert TokenRequest(token="x" * 30, password=password).password == password
    assert verify_password(password, hash_password(password))
