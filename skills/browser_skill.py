from .base_skill import BaseSkill
import webbrowser

class BrowserSkill(BaseSkill):
    @property
    def skill_id(self):
        return "browser"
    
    @property
    def description(self):
        return "Web browser control: open URLs, search web"
    
    @property
    def version(self):
        return "1.0.0"
    
    def can_handle(self, query: str):
        query_lower = query.lower()
        browser_keywords = ["open browser", "go to", "search for", "search web", "open website", "browse to"]
        if any(k in query_lower for k in browser_keywords):
            return 1.0
        return 0.0
    
    def handle(self, query: str, params=None):
        try:
            query_lower = query.lower()
            
            # Search web
            if any(k in query_lower for k in ["search for", "search web"]):
                search_term = query_lower
                for k in ["search for", "search web", "search the web for"]:
                    search_term = search_term.replace(k, "").strip()
                if search_term:
                    url = f"https://duckduckgo.com/?q={search_term.replace(' ', '+')}"
                    webbrowser.open(url)
                    return f"Searching for '{search_term}'..."
            
            # Open website
            url = None
            if "http" in query or "www" in query:
                # Try to extract URL
                words = query.split()
                for word in words:
                    if "http" in word or "www" in word:
                        url = word
                        if not url.startswith("http"):
                            url = "https://" + url
                        break
            
            if not url and any(k in query_lower for k in ["open browser", "go to", "open website", "browse to"]):
                # Default to Google if no URL
                url = "https://google.com"
            
            if url:
                webbrowser.open(url)
                return f"Opening {url}"
            
            return "Browser ready"
        except Exception as e:
            return f"Browser error: {str(e)}"
