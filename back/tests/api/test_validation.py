import pytest

from app.schemas import check_name, check_password_strength


@pytest.mark.parametrize(
    "password",
    ["alllowercase1!", "ALLUPPERCASE1!", "NoDigitsHere!", "NoSpecial123"],
)
def test_weak_passwords_are_rejected(password):
    with pytest.raises(ValueError):
        check_password_strength(password)


def test_strong_password_is_accepted():
    assert check_password_strength("Sup3r-secret!") == "Sup3r-secret!"


@pytest.mark.parametrize("name", ["Chloé", "Jean-Luc", "O'Neil", "Mary Ann"])
def test_valid_names(name):
    assert check_name(name) == name


@pytest.mark.parametrize("name", ["<script>", "Bob1", "a@b"])
def test_invalid_names(name):
    with pytest.raises(ValueError):
        check_name(name)
