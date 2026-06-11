class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Permissions-Policy (modern)
        response["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"

        # Deprecated but still required by some scanners:
        response["Feature-Policy"] = (
            "geolocation 'none'; camera 'none'; microphone 'none'"
        )

        return response
