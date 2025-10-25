from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

class CustomCSPMiddleware(MiddlewareMixin):
    """
    A simple middleware to ensure the Content-Security-Policy header is 
    explicitly added to the response, acting as a fallback for django-csp 
    if the header is being stripped by the environment (Render/Cloudflare).
    
    This correctly reads the directives from the CONTENT_SECURITY_POLICY['DIRECTIVES'] setting.
    """
    def __init__(self, get_response):
        super().__init__(get_response)
        
        # ✅ FIX: Get directives from the 'DIRECTIVES' key as used in settings.py
        directives = settings.CONTENT_SECURITY_POLICY.get('DIRECTIVES', {})
        csp_parts = []
        
        # Build the final CSP string
        for directive, sources in directives.items():
            # Sources are expected to be a tuple/list of strings
            source_string = ' '.join(sources)
            csp_parts.append(f"{directive} {source_string}")
        
        self.csp_header_value = '; '.join(csp_parts)

    def process_response(self, request, response):
        """
        Add the Content-Security-Policy header to the response if it's missing.
        """
        # Only apply the header if it hasn't been set by the django-csp middleware
        if self.csp_header_value and 'Content-Security-Policy' not in response:
            response['Content-Security-Policy'] = self.csp_header_value
        
        return response