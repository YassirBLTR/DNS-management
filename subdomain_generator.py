import random
from typing import List, Dict

# Predefined main domains from your service
MAIN_DOMAINS = [
    "accesscam.org",
    "camdvr.org", 
    "casacam.net",
    "ddnsfree.com",
    "ddnsgeek.com",
    "freeddns.org",
    "giize.com",
    "gleeze.com",
    "kozow.com",
    "loseyourip.com",
    "mywire.org",
    "ooguy.com",
    "theworkpc.com",
    "webredirect.org",
    "1cooldns.com",
    "bumbleshrimp.com",
    "dynu.net",
    "dynuddns.com",
    "ddnsguru.com",
    "mysynology.net"
]

# Dictionary for subdomain generation
SUBDOMAIN_DICTIONARY = {
    "prefixes": [
        "my", "home", "office", "work", "dev", "test", "demo", "app", "web", "api",
        "secure", "private", "public", "main", "primary", "backup", "temp", "local",
        "remote", "cloud", "mobile", "desktop", "server", "client", "admin", "user",
        "guest", "live", "stage", "prod", "beta", "alpha", "v1", "v2", "new", "old"
    ],
    "words": [
        "camera", "monitor", "device", "system", "network", "server", "client", "hub",
        "gateway", "router", "switch", "access", "control", "security", "stream",
        "video", "audio", "data", "file", "backup", "storage", "cloud", "sync",
        "share", "connect", "link", "bridge", "tunnel", "proxy", "cache", "queue",
        "service", "app", "tool", "utility", "helper", "manager", "viewer", "editor",
        "player", "recorder", "scanner", "detector", "sensor", "alarm", "alert",
        "notify", "message", "mail", "chat", "voice", "call", "meeting", "conference"
    ],
    "suffixes": [
        "cam", "dvr", "nvr", "cctv", "ip", "hd", "4k", "pro", "plus", "max", "mini",
        "lite", "basic", "advanced", "premium", "standard", "custom", "special",
        "secure", "safe", "guard", "watch", "view", "see", "look", "eye", "lens",
        "focus", "zoom", "pan", "tilt", "fixed", "mobile", "wireless", "wired",
        "indoor", "outdoor", "night", "day", "auto", "manual", "smart", "ai",
        "cloud", "local", "remote", "direct", "live", "record", "playback", "archive"
    ]
}

class SubdomainGenerator:
    def __init__(self):
        self.main_domains = MAIN_DOMAINS
        self.dictionary = SUBDOMAIN_DICTIONARY
    
    def get_main_domains(self) -> List[str]:
        """Get list of available main domains"""
        return self.main_domains.copy()
    
    def generate_subdomain_name(self, use_prefix: bool = True, use_suffix: bool = True) -> str:
        """Generate a random subdomain name using the dictionary"""
        parts = []
        
        if use_prefix and random.choice([True, False]):
            parts.append(random.choice(self.dictionary["prefixes"]))
        
        # Always include a main word
        parts.append(random.choice(self.dictionary["words"]))
        
        if use_suffix and random.choice([True, False]):
            parts.append(random.choice(self.dictionary["suffixes"]))
        
        # If we only have one part, add another to make it more interesting
        if len(parts) == 1:
            if random.choice([True, False]):
                parts.insert(0, random.choice(self.dictionary["prefixes"]))
            else:
                parts.append(random.choice(self.dictionary["suffixes"]))
        
        return "-".join(parts)
    
    def generate_subdomains(self, main_domain: str, count: int = 10, 
                          use_prefix: bool = True, use_suffix: bool = True) -> List[str]:
        """Generate multiple unique subdomains for a main domain"""
        if main_domain not in self.main_domains:
            raise ValueError(f"Main domain '{main_domain}' is not in the allowed list")
        
        subdomains = set()
        max_attempts = count * 3  # Prevent infinite loop
        attempts = 0
        
        while len(subdomains) < count and attempts < max_attempts:
            subdomain_name = self.generate_subdomain_name(use_prefix, use_suffix)
            full_subdomain = f"{subdomain_name}.{main_domain}"
            subdomains.add(full_subdomain)
            attempts += 1
        
        return list(subdomains)
    
    def create_custom_subdomain(self, subdomain_name: str, main_domain: str) -> str:
        """Create a custom subdomain with validation"""
        if main_domain not in self.main_domains:
            raise ValueError(f"Main domain '{main_domain}' is not in the allowed list")
        
        # Basic validation for subdomain name
        if not subdomain_name:
            raise ValueError("Subdomain name cannot be empty")
        
        # Remove invalid characters and convert to lowercase
        subdomain_name = subdomain_name.lower().strip()
        
        # Replace spaces and invalid characters with hyphens
        import re
        subdomain_name = re.sub(r'[^a-z0-9-]', '-', subdomain_name)
        subdomain_name = re.sub(r'-+', '-', subdomain_name)  # Remove multiple hyphens
        subdomain_name = subdomain_name.strip('-')  # Remove leading/trailing hyphens
        
        if not subdomain_name:
            raise ValueError("Subdomain name contains only invalid characters")
        
        if len(subdomain_name) > 63:
            raise ValueError("Subdomain name is too long (max 63 characters)")
        
        return f"{subdomain_name}.{main_domain}"
    
    def get_random_suggestions(self, count: int = 5) -> List[Dict[str, str]]:
        """Get random subdomain suggestions with different main domains"""
        suggestions = []
        
        for _ in range(count):
            main_domain = random.choice(self.main_domains)
            subdomain_name = self.generate_subdomain_name()
            full_subdomain = f"{subdomain_name}.{main_domain}"
            
            suggestions.append({
                "subdomain": subdomain_name,
                "main_domain": main_domain,
                "full_domain": full_subdomain
            })
        
        return suggestions
