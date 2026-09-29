import json
import os
import stat

import pytest

from btc_perp_bot.core import BotError
from btc_perp_bot.wallet import create_wallet, load_wallet, password_from_file, verify_wallet


@pytest.fixture(scope="module")
def wallet(tmp_path_factory):
    path = tmp_path_factory.mktemp("wallet") / "wallet.keystore.json"
    password = "test-only-password-not-for-real-funds"
    result = create_wallet(path, password)
    return path, password, result


def test_encrypted_wallet_can_sign_and_recover_without_exposing_key(wallet):
    path, password, public = wallet
    signer = load_wallet(path, password, "testnet")
    assert signer.address == public["address"]
    assert verify_wallet(signer)["local_signature_verified"] is True
    text = path.read_text()
    assert signer.key.hex() not in text
    assert password not in text
    assert json.loads(text)["crypto"]["kdf"] == "scrypt"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_wrong_password_and_wrong_network_fail(wallet):
    path, password, _ = wallet
    with pytest.raises(BotError, match="unlock"):
        load_wallet(path, "wrong-password-long-enough")
    with pytest.raises(BotError, match="purpose"):
        load_wallet(path, password, "mainnet")


def test_wallet_is_never_overwritten(wallet):
    path, password, _ = wallet
    before = path.read_bytes()
    with pytest.raises(BotError, match="overwrite"):
        create_wallet(path, password)
    assert path.read_bytes() == before


def test_refuse_symlinks_and_world_readable_passwords(tmp_path):
    secret = tmp_path / "password"
    secret.write_text("unit-test-password-only")
    secret.chmod(0o644)
    with pytest.raises(BotError, match="0600"):
        password_from_file(secret)
    secret.chmod(0o600)
    link = tmp_path / "link"
    link.symlink_to(secret)
    with pytest.raises(OSError):
        password_from_file(link)
    with pytest.raises(BotError, match="overwrite"):
        create_wallet(link, "long-test-password")


def test_weak_password_refused_before_writing(tmp_path):
    dest = tmp_path / "not-created.json"
    with pytest.raises(BotError):
        create_wallet(dest, "short")
    assert not dest.exists()
