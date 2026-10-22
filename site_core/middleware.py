from django.http import HttpResponsePermanentRedirect


class LegacyUploadsRedirectMiddleware:
    """Old WordPress image links (/wp-content/uploads/...) keep working after the move."""

    PREFIX = "/wp-content/uploads/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(self.PREFIX):
            return HttpResponsePermanentRedirect("/media/uploads/" + request.path[len(self.PREFIX):])
        return self.get_response(request)
