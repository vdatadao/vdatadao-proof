import hashlib
import json
import logging
import os
from typing import Dict, Any

from my_proof.models.proof_response import ProofResponse
from my_proof.utils.blockchain import BlockchainClient
from my_proof.utils.google import get_google_user
from my_proof.utils.schema import validate_schema
from my_proof.config import settings


class Proof:
    def __init__(self):
        self.proof_response = ProofResponse(dlp_id=settings.DLP_ID)
        try:
            self.blockchain_client = BlockchainClient()
            self.blockchain_available = True
        except Exception as e:
            logging.warning(f"Blockchain client initialization failed: {str(e)}")
            self.blockchain_available = False

    def _calculate_instagram_quality_score(self, input_data: Dict[str, Any]) -> float:
        """Instagram verisi için kalite puanı hesaplama (0-35)"""
        score = 0.0
        
        # Schema uyumluluğu (0-15 puan)
        schema_score = 15.0 if self._validate_instagram_schema(input_data) else 0.0
        score += schema_score
        
        # Veri tutarlılığı (0-10 puan)
        consistency_score = self._check_instagram_consistency(input_data) * 10.0
        score += consistency_score
        
        # Veri kapsamı (0-10 puan)
        coverage_score = self._calculate_instagram_coverage(input_data) * 10.0
        score += coverage_score
        
        return min(score, 35.0)  # Maksimum 35 puan
    
    def _validate_instagram_schema(self, input_data: Dict[str, Any]) -> bool:
        """Instagram schema doğrulaması"""
        try:
            schema_type, schema_matches = validate_schema(input_data)
            return schema_matches and schema_type == "instagram-profile.json"
        except:
            return False
    
    def _check_instagram_consistency(self, input_data: Dict[str, Any]) -> float:
        """Instagram verisi tutarlılık kontrolü"""
        score = 0.0
        checks = 0
        
        # Takipçi sayısı kontrolü
        followers = input_data.get('profile', {}).get('followersCount', 0)
        if isinstance(followers, (int, float)) and followers >= 0:
            score += 1.0
        checks += 1
        
        # Takip edilen sayısı kontrolü
        following = input_data.get('profile', {}).get('followingCount', 0)
        if isinstance(following, (int, float)) and following >= 0:
            score += 1.0
        checks += 1
        
        # Post sayısı kontrolü
        posts_count = input_data.get('profile', {}).get('postsCount', 0)
        if isinstance(posts_count, (int, float)) and posts_count >= 0:
            score += 1.0
        checks += 1
        
        # Timestamp kontrolü
        timestamp = input_data.get('timestamp', 0)
        if isinstance(timestamp, (int, float)) and timestamp > 0:
            score += 1.0
        checks += 1
        
        # Username format kontrolü
        username = input_data.get('username', '')
        if isinstance(username, str) and len(username) > 0 and not username.isspace():
            score += 1.0
        checks += 1
        
        return score / checks if checks > 0 else 0.0
    
    def _calculate_instagram_coverage(self, input_data: Dict[str, Any]) -> float:
        """Instagram verisi kapsam puanı"""
        score = 0.0
        total_fields = 0
        
        # Temel profil bilgileri
        profile = input_data.get('profile', {})
        basic_fields = ['fullName', 'biography', 'website', 'isPrivate', 'isVerified']
        for field in basic_fields:
            if field in profile:
                score += 1.0
            total_fields += 1
        
        # İstatistik bilgileri
        stats_fields = ['followersCount', 'followingCount', 'postsCount']
        for field in stats_fields:
            if field in profile and profile[field] is not None:
                score += 1.0
            total_fields += 1
        
        # Posts verisi
        posts = input_data.get('posts', [])
        if posts and len(posts) > 0:
            score += 1.0
        total_fields += 1
        
        # Metadata bilgileri
        metadata = input_data.get('metadata', {})
        meta_fields = ['source', 'collectionDate', 'dataType']
        for field in meta_fields:
            if field in metadata:
                score += 1.0
            total_fields += 1
        
        return score / total_fields if total_fields > 0 else 0.0
    
    def _calculate_instagram_authenticity_score(self, google_user, input_data: Dict[str, Any], is_drive_upload: bool = False) -> float:
        """Instagram verisi orijinallik puanı (0-30)"""
        score = 0.0
        
        # Google OAuth doğrulaması (0-20 puan)
        if google_user:
            score += 20.0
        
        # Dosya bütünlüğü kontrolü (0-10 puan)
        file_integrity_score = self._check_file_integrity(input_data) * 10.0
        score += file_integrity_score
        
        return min(score, 30.0)  # Maksimum 30 puan
    
    def _check_file_integrity(self, input_data: Dict[str, Any]) -> float:
        """Dosya bütünlüğü kontrolü"""
        # Basit kontroller
        if not input_data:
            return 0.0
        
        # Gerekli alanların varlığı
        required_fields = ['userId', 'username', 'timestamp', 'profile', 'metadata']
        present_fields = sum(1 for field in required_fields if field in input_data)
        
        return present_fields / len(required_fields)
    
    def _calculate_instagram_uniqueness_score(self, input_data: Dict[str, Any]) -> float:
        """Instagram verisi benzersizlik puanı (0-20)"""
        score = 0.0
        
        # Kullanıcı benzersizliği (0-10 puan)
        user_uniqueness = self._check_user_uniqueness()
        score += user_uniqueness * 10.0
        
        # İçerik benzersizliği (0-10 puan)
        content_uniqueness = self._check_content_uniqueness(input_data)
        score += content_uniqueness * 10.0
        
        return min(score, 20.0)  # Maksimum 20 puan
    
    def _check_user_uniqueness(self) -> float:
        """Kullanıcı benzersizliği kontrolü"""
        if self.blockchain_available and settings.OWNER_ADDRESS:
            existing_file_count = self.blockchain_client.get_contributor_file_count()
            if existing_file_count == 0:
                return 1.0  # İlk katkı
            else:
                return 0.5  # Tekrar katkı (daha düşük puan)
        else:
            return 1.0  # Blockchain kontrolü yoksa varsayılan

    def _check_content_uniqueness(self, input_data: Dict[str, Any]) -> float:
        """İçerik benzersizliği kontrolü"""
        user_id = input_data.get('userId')
        username = input_data.get('username')
        
        if not user_id or not username:
            return 0.0
        
        if self.blockchain_available:
            # Blockchain'de aynı userId/username kombinasyonu var mı kontrol et
            try:
                is_unique_content = self.blockchain_client.check_content_uniqueness(user_id, username)
                return 1.0 if is_unique_content else 0.3  # Aynı içerik varsa düşük puan
            except Exception as e:
                logging.warning(f"Content uniqueness check failed: {str(e)}")
                return 0.7  # Kontrol başarısızsa orta puan
        else:
            return 1.0  # Blockchain kontrolü yoksa varsayılan
    
    def _calculate_instagram_ownership_score(self, google_user, is_drive_upload: bool = False) -> float:
        """Instagram verisi sahiplik puanı (0-15)"""
        score = 0.0
        
        # Google OAuth kimlik doğrulaması (0-10 puan)
        if google_user:
            score += 10.0
        
        # Drive sahipliği (0-5 puan)
        if google_user and is_drive_upload:
            score += 5.0  # Drive'dan yükleme extra puan
        
        return min(score, 15.0)  # Maksimum 15 puan
    
    def _calculate_profile_completeness(self, input_data: Dict[str, Any]) -> float:
        """Profil tamamlık oranı"""
        profile = input_data.get('profile', {})
        total_fields = 0
        filled_fields = 0
        
        # Profil alanları
        profile_fields = ['fullName', 'biography', 'website', 'isPrivate', 'isVerified', 
                         'followersCount', 'followingCount', 'postsCount']
        
        for field in profile_fields:
            total_fields += 1
            if field in profile and profile[field] is not None:
                filled_fields += 1
        
        return filled_fields / total_fields if total_fields > 0 else 0.0

    def generate(self) -> ProofResponse:
        """Generate proofs for all input files."""
        logging.info("Starting proof generation")
        errors = []

        # Fetch Google user info if token is provided
        google_user = None
        if settings.GOOGLE_TOKEN:
            google_user = get_google_user()
            if not google_user:
                errors.append("UNVERIFIED_STORAGE_USER")
        else:
            logging.info("GOOGLE_TOKEN not set, skipping user verification")

        # Drive upload kontrolü
        is_drive_upload = self._check_if_drive_upload()

        # Iterate through files and calculate data validity
        for input_filename in os.listdir(settings.INPUT_DIR):
            logging.info(f"Checking file: {input_filename}")
            input_file = os.path.join(settings.INPUT_DIR, input_filename)

            if os.path.splitext(input_file)[1].lower() == '.json':
                with open(input_file, 'r') as f:
                    json_content = f.read()
                    input_data = json.loads(json_content)
                    schema_type, schema_matches = validate_schema(input_data)
                    
                    if not schema_matches:
                        errors.append(f"INVALID_SCHEMA")
                        break
                    
                    # Instagram için puanlama (artık sadece Instagram)
                    # Google OAuth kontrolü
                    if not google_user:
                        errors.append("NO_GOOGLE_OAUTH")
                        logging.warning("Instagram data requires Google OAuth for verification")
                    
                    self.proof_response.quality = self._calculate_instagram_quality_score(input_data)
                    self.proof_response.authenticity = self._calculate_instagram_authenticity_score(google_user, input_data, is_drive_upload)
                    self.proof_response.uniqueness = self._calculate_instagram_uniqueness_score(input_data)
                    self.proof_response.ownership = self._calculate_instagram_ownership_score(google_user, is_drive_upload)

                    # Instagram için özel attributes
                    self.proof_response.attributes = {
                        'schema_type': schema_type,
                        'user_id': input_data.get('userId'),
                        'username': input_data.get('username'),
                        'verified_via_oauth': google_user is not None,
                        'uploaded_via_drive': is_drive_upload,
                        'instagram_api_available': False,
                        'data_coverage': self._calculate_instagram_coverage(input_data),
                        'data_consistency': self._check_instagram_consistency(input_data),
                        'posts_count': len(input_data.get('posts', [])),
                        'profile_completeness': self._calculate_profile_completeness(input_data),
                        'user_uniqueness': self._check_user_uniqueness(),
                        'content_uniqueness': self._check_content_uniqueness(input_data),
                        'total_uniqueness_score': self._calculate_instagram_uniqueness_score(input_data),
                        'platform': 'instagram',
                        'verification_method': 'google_oauth',
                        'upload_method': 'google_drive' if is_drive_upload else 'manual'
                    }

                    # Calculate overall score (100 üzerinden)
                    base_score = (
                        self.proof_response.quality + 
                        self.proof_response.authenticity + 
                        self.proof_response.uniqueness + 
                        self.proof_response.ownership
                    )
                    
                    # NO_GOOGLE_OAUTH cezası uygula
                    if "NO_GOOGLE_OAUTH" in errors:
                        penalty = base_score * 0.90  # %90 ceza
                        self.proof_response.score = base_score - penalty
                        logging.warning(f"Applied 90% penalty for NO_GOOGLE_OAUTH. Base score: {base_score}, Final score: {self.proof_response.score}")
                    else:
                        self.proof_response.score = base_score
                    
                    # Additional metadata about the proof, written onchain
                    self.proof_response.metadata = {
                        'schema_type': schema_type,
                        'platform': 'instagram',
                        'verification_method': 'google_oauth',
                        'upload_method': 'google_drive' if is_drive_upload else 'manual',
                        'scoring_system': '100_point_scale',
                        'penalty_applied': "NO_GOOGLE_OAUTH" if "NO_GOOGLE_OAUTH" in errors else None
                    }
                    
                    self.proof_response.valid = len(errors) == 0
        
        # Only include errors if there are any
        if len(errors) > 0:
            self.proof_response.attributes['errors'] = errors

        return self.proof_response
        
    def _check_if_drive_upload(self) -> bool:
        """Dosyanın Drive'dan yüklenip yüklenmediğini kontrol et"""
        # Environment variable'dan kontrol
        if hasattr(settings, 'UPLOAD_SOURCE') and settings.UPLOAD_SOURCE == 'google_drive':
            return True
        
        # Dosya yolundan kontrol (örnek)
        # Gerçek implementasyonda bu kısım UI'dan gelen bilgiye göre ayarlanmalı
        return False

