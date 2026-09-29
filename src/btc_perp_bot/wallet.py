import json
import os
from pathlib import Path

from eth_account import Account
from eth_account.messages import encode_defunct

from .core import BotError, private_open, write_private_json


def password_from_file(path):
    with os.fdopen(private_open(path, os.O_RDONLY), "r") as src:
        password = src.read(4097).rstrip("\r\n")
    if not 12 <= len(password) <= 4096:
        raise BotError("Password must contain 12 to 4096 characters")
    return password


def create_wallet(path, password, purpose="testnet"):
    if purpose not in {"testnet", "mainnet"} or not 12 <= len(password) <= 4096:
        raise BotError("Invalid wallet purpose or password (minimum 12 characters)")
    path = Path(path).expanduser()
    if path.exists() or path.is_symlink():
        raise BotError("Wallet already exists; refusing to overwrite")
    account = Account.create()
    encrypted = Account.encrypt(account.key, password, kdf="scrypt", iterations=2**18)
    encrypted["btc_perp_bot"] = {"purpose": purpose, "format": 1}
    write_private_json(path, encrypted)
    return {"address": account.address, "keystore": str(path), "purpose": purpose}


def load_wallet(path, password, purpose=None):
    with os.fdopen(private_open(path, os.O_RDONLY), "r") as src:
        data = json.load(src)
    saved_purpose = data.get("btc_perp_bot", {}).get("purpose")
    if purpose is not None and saved_purpose != purpose:
        raise BotError("Keystore purpose does not match the execution network")
    try:
        account = Account.from_key(Account.decrypt(data, password))
    except Exception as exc:
        raise BotError("Could not unlock keystore (wrong password or damaged file)") from exc
    if account.address.lower().removeprefix("0x") != data.get("address", "").lower().removeprefix("0x"):
        raise BotError("Keystore address does not match decrypted key")
    return account


def verify_wallet(account):
    # This is a local message signature, NOT an exchange order or chain transaction.
    message = encode_defunct(text="btc-perp-bot: local keystore verification only")
    signed = account.sign_message(message)
    recovered = Account.recover_message(message, signature=signed.signature)
    return {"address": account.address, "local_signature_verified": recovered == account.address}
