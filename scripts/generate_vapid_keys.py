import base64

from cryptography.hazmat.primitives.asymmetric import ec


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def main() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_numbers = private_key.private_numbers()
    public_numbers = private_key.public_key().public_numbers()

    private_bytes = private_numbers.private_value.to_bytes(32, "big")
    public_bytes = (
        b"\x04"
        + public_numbers.x.to_bytes(32, "big")
        + public_numbers.y.to_bytes(32, "big")
    )

    print(f"PUSH_VAPID_PUBLIC_KEY={_base64url(public_bytes)}")
    print(f"PUSH_VAPID_PRIVATE_KEY={_base64url(private_bytes)}")


if __name__ == "__main__":
    main()
