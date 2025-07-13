import requests
import logging
from typing import Optional

class GoogleUserInfo:
    def __init__(self, id: str, email: str, name: str, verified_email: bool = True):
        self.id = id
        self.email = email
        self.name = name
        self.verified_email = verified_email

def get_google_user() -> Optional[GoogleUserInfo]:
    """
    Google OAuth token ile kullanıcı bilgisi al.
    Instagram doğrulaması ve Drive erişimi için kullanılır.
    """
    try:
        from my_proof.config import settings
        
        if not settings.GOOGLE_TOKEN:
            logging.warning("No Google token provided")
            return None
        
        # Test modu kontrolünü kaldır
        if settings.GOOGLE_TOKEN.startswith("test_"):
            logging.warning("Test tokens not allowed in production")
            return None
            
        # Gerçek Google API çağrısı
        headers = {
            'Authorization': f'Bearer {settings.GOOGLE_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            user_data = response.json()
            return GoogleUserInfo(
                id=user_data.get('id', ''),
                email=user_data.get('email', ''),
                name=user_data.get('name', ''),
                verified_email=user_data.get('verified_email', True)
            )
        else:
            logging.error(f"Google API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logging.error(f"Failed to get Google user: {str(e)}")
        return None
