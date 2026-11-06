from typing import Protocol


class MailTransport(Protocol):
    def submit(self, recipient: str, subject: str, body: str) -> str:
        ...


class InMemoryTransport:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def submit(self, recipient: str, subject: str, body: str) -> str:
        self.sent.append((recipient, subject, body))
        return f"mail-{len(self.sent)}"
