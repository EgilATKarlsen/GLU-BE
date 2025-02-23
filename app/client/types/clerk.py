from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# Models for verification types and other "object" types are represented generically.
VerificationType = Optional[Dict[str, Any]]
Metadata = Dict[str, Any]


IdentificationLink = Dict[str, Any]


class EmailAddress(BaseModel):
    id: str
    object: str  # Expected to be "email_address"
    email_address: str
    reserved: bool
    verification: VerificationType  # OTP, Admin, or FromOAuth (object or null)
    linked_to: List[IdentificationLink]
    matches_sso_connection: bool
    created_at: int  # Unix timestamp (int64)
    updated_at: int  # Unix timestamp (int64)


class PhoneNumber(BaseModel):
    id: str
    object: str  # Expected to be "phone_number"
    phone_number: str
    reserved_for_second_factor: bool
    default_second_factor: bool
    reserved: bool
    verification: VerificationType  # OTP or Admin (object or null)
    linked_to: List[IdentificationLink]
    backup_codes: Optional[List[str]]  # Array of strings or null
    created_at: int  # Unix timestamp (int64)
    updated_at: int  # Unix timestamp (int64)


class OauthVerification(BaseModel):
    status: str
    strategy: str
    attempts: Optional[int] = None
    expire_at: Optional[int] = None


class ExternalAccount(BaseModel):
    object: str
    id: str
    provider: str
    identification_id: str
    provider_user_id: str
    approved_scopes: str
    email_address: str
    first_name: str
    last_name: str
    avatar_url: str
    image_url: Optional[str] = None
    username: Optional[str] = None
    public_metadata: Metadata
    label: Optional[str] = None
    created_at: int
    updated_at: int
    verification: OauthVerification


class User(BaseModel):
    id: str
    object: str  # Expected to be "user"
    external_id: Optional[str] = None
    primary_email_address_id: Optional[str] = None
    primary_phone_number_id: Optional[str] = None
    primary_web3_wallet_id: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    profile_image_url: str
    image_url: str  # Deprecated field but still provided in the response
    has_image: bool
    public_metadata: Metadata
    private_metadata: Optional[Metadata] = None
    unsafe_metadata: Metadata

    email_addresses: List[EmailAddress]
    phone_numbers: List[PhoneNumber]
    web3_wallets: List[Dict[str, Any]]
    passkeys: List[Dict[str, Any]]
    external_accounts: List[ExternalAccount]
    saml_accounts: List[Dict[str, Any]]

    banned: bool
    locked: bool
    lockout_expires_in_seconds: Optional[int] = None  # Unix timestamp or null
    verification_attempts_remaining: Optional[int] = None  # int64 or null
    updated_at: int  # Unix timestamp (int64)
    created_at: int  # Unix timestamp (int64)
    delete_self_enabled: bool
    create_organization_enabled: bool
    create_organizations_limit: Optional[int] = None  # 0 means unlimited, or null
    last_active_at: Optional[int] = None  # Unix timestamp (int64) or null
    legal_accepted_at: Optional[int] = None  # Unix timestamp (int64) or null
