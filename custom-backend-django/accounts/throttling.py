from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    # Separate scope from DRF's default anon throttle so login isn't
    # accidentally sharing a budget with other public endpoints.
    scope = "login"


class RegisterRateThrottle(AnonRateThrottle):
    # Own budget for account creation, so a burst of signups can't starve
    # (or be starved by) the anonymous rate limit shared with other endpoints.
    scope = "register"