"""Tests for the HTML login-form parser."""

import pytest

from myvw.client import LoginError, _parse_form


def test_parse_form_extracts_action_and_fields():
    html = """
    <html><body>
      <form action="/signin/authenticate" method="post">
        <input type="hidden" name="csrf" value="abc123">
        <input type="text" name="username" value="">
        <input type="password" name="password" value="">
      </form>
    </body></html>
    """
    action, fields = _parse_form(html, base_url="https://identity.vwgroup.io/login")

    assert action == "https://identity.vwgroup.io/signin/authenticate"
    assert fields == {"csrf": "abc123", "username": "", "password": ""}


def test_parse_form_uses_absolute_action_as_is():
    html = '<form action="https://identity.vwgroup.io/other/path"><input name="x" value="1"></form>'
    action, fields = _parse_form(html, base_url="https://identity.vwgroup.io/login")

    assert action == "https://identity.vwgroup.io/other/path"
    assert fields == {"x": "1"}


def test_parse_form_falls_back_to_base_url_when_action_missing():
    html = '<form><input name="x" value="1"></form>'
    action, fields = _parse_form(html, base_url="https://identity.vwgroup.io/login")

    assert action == "https://identity.vwgroup.io/login"
    assert fields == {"x": "1"}


def test_parse_form_ignores_inputs_outside_form():
    html = """
    <input name="outside" value="ignored">
    <form action="/go"><input name="inside" value="kept"></form>
    """
    _, fields = _parse_form(html, base_url="https://identity.vwgroup.io/login")

    assert fields == {"inside": "kept"}


def test_parse_form_action_comes_from_first_form_only():
    # Characterization test: the parser locks in the *action* of the first
    # <form> it sees, but keeps collecting <input> fields for as long as it
    # is inside any form tag afterwards (it does not scope fields per-form).
    html = """
    <form action="/first"><input name="a" value="1"></form>
    <form action="/second"><input name="b" value="2"></form>
    """
    action, fields = _parse_form(html, base_url="https://identity.vwgroup.io/login")

    assert action == "https://identity.vwgroup.io/first"
    assert fields == {"a": "1", "b": "2"}


def test_parse_form_input_without_name_is_skipped():
    html = '<form action="/go"><input value="no-name-here"><input name="kept" value="1"></form>'
    _, fields = _parse_form(html, base_url="https://identity.vwgroup.io/login")

    assert fields == {"kept": "1"}


def test_parse_form_raises_login_error_when_no_form_present():
    html = "<html><body><p>No form here.</p></body></html>"

    with pytest.raises(LoginError):
        _parse_form(html, base_url="https://identity.vwgroup.io/login")
