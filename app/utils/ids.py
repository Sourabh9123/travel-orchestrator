from uuid import UUID, uuid4


def new_uuid() -> UUID:
    """Create a new random UUID value."""

    return uuid4()
