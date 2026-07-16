from uuid import UUID


def valid_uuid(s: str) -> bool:
    try:
        UUID(s)
        return True
    except ValueError:
        return False
