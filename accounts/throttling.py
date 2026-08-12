from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    # Separate scope from DRF's default anon throttle so login isn't
    # accidentally sharing a budget with other public endpoints.
    scope = "login"