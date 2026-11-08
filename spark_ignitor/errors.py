class DeviceError(Exception):
    """A device refused a command or did not answer."""
class TripError(Exception):
    """A safety check fired. The run stops and everything is switched off."""
class Stopped(Exception):
    """The operator pressed STOP. Not an error: the run ends cleanly."""
class ScopeTimeout(DeviceError):
    """The scope never saw a trigger."""
