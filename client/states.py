from collections import deque
from enum import Enum


class State(Enum):
    HIDDEN = "hidden"
    PEEKING = "peeking"
    ENTERING = "entering"
    WAITING = "waiting"
    READING = "reading"
    LEAVING = "leaving"


class Capivara:
    def __init__(self):
        self.state = State.HIDDEN
        self.pile: deque[dict] = deque()
        self.seen: set[int] = set()
        self.held = False

    @property
    def current(self) -> dict | None:
        return self.pile[0] if self.pile else None

    def message(self, msg: dict) -> None:
        if msg["id"] in self.seen:
            return
        self.seen.add(msg["id"])
        self.pile.append(msg)
        if not self.held and self.state in (State.HIDDEN, State.PEEKING, State.LEAVING):
            self.state = State.ENTERING

    def hold(self) -> None:
        self.held = True

    def release(self) -> None:
        self.held = False
        if self.pile and self.state in (State.HIDDEN, State.PEEKING):
            self.state = State.ENTERING

    def hover_in(self) -> None:
        if self.state == State.HIDDEN:
            self.state = State.PEEKING

    def hover_out(self) -> None:
        if self.state == State.PEEKING:
            self.state = State.HIDDEN

    def send_off(self) -> None:
        if self.state == State.PEEKING:
            self.state = State.LEAVING

    def click(self) -> None:
        if self.state == State.WAITING and self.pile:
            self.state = State.READING

    def note_closed(self) -> dict | None:
        if self.state != State.READING:
            return None
        read = self.pile.popleft()
        self.state = State.WAITING if self.pile else State.LEAVING
        return read

    def arrived(self) -> None:
        if self.state == State.ENTERING:
            self.state = State.WAITING

    def gone(self) -> None:
        if self.state == State.LEAVING:
            self.state = State.ENTERING if self.pile and not self.held else State.HIDDEN
