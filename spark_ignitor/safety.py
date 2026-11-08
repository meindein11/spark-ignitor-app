class Safety:
    """Returns a reason text when any interlock fires, otherwise None."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.misfire_run = 0

    def reset(self):
        self.misfire_run = 0

    def check_setpoint(self, vset, dwell_us):
        if dwell_us > self.cfg.max_dwell_us:
            return f"dwell {dwell_us} us is above the limit of {self.cfg.max_dwell_us} us"
        if vset > self.cfg.max_voltage_V:
            return f"voltage {vset} V is above the limit of {self.cfg.max_voltage_V} V"
        return None

    def check_shot(self, ipk_A, misfire, vset, vread):
        c = self.cfg
        if ipk_A > c.I_trip_A:
            return f"peak current {ipk_A:.1f} A is above the trip level of {c.I_trip_A} A"
        if vread is not None and abs(vread - vset) > c.vread_tolerance_V:
            return f"Rigol reads {vread:.2f} V but {vset:.2f} V was set"
        self.misfire_run = self.misfire_run + 1 if misfire else 0
        if self.misfire_run >= c.misfires_to_trip:
            return f"{self.misfire_run} misfires in a row"
        return None
