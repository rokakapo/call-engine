from enum import Enum
from time import perf_counter


class CallState(str, Enum): IDLE="idle"; DIALING="dialing"; CONNECTED="connected"; ENDED="ended"

class CallController:
    def __init__(self, logger):
        self.logger, self.state, self.number, self.started = logger, CallState.IDLE, "", None

    def dial(self, number: str):
        if not number.strip(): raise ValueError("Phone number is required")
        self.number, self.state, self.started = number, CallState.DIALING, perf_counter()
        self.logger.info("Dial requested: %s", number)
        # The production HFP adapter issues ATD on the selected gateway.
        return self.snapshot()

    def connect(self):
        if self.state != CallState.DIALING: raise ValueError("No outbound call is dialing")
        self.state = CallState.CONNECTED; self.logger.info("Call connected")
        return self.snapshot()

    def hangup(self):
        self.state = CallState.ENDED; self.logger.info("Call ended")
        return self.snapshot()

    def snapshot(self):
        latency = round((perf_counter() - self.started) * 1000) if self.started else None
        return {"state": self.state.value, "number": self.number, "setup_latency_ms": latency}
