from datetime import datetime, timezone

from extensions import db


def uid(length=36):
    return uuid4hex(length)


def uuid4hex(length):
    import uuid

    return str(uuid.uuid4())[:length]


def now():
    return datetime.now(timezone.utc)


class Organization(db.Model):
    __tablename__ = "organizations"

    id = db.Column(db.String(36), primary_key=True, default=uid)
    name = db.Column(db.String(150), nullable=False)
    legal_id = db.Column(db.String(50), nullable=False)
    country = db.Column(db.String(100), nullable=False, default="Maroc")
    city = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    address = db.Column(db.Text, nullable=False)
    website = db.Column(db.String(255))
    email = db.Column(db.String(255), nullable=False)

    status = db.Column(db.String(20), nullable=False, default="PENDING")
    reviewed_by = db.Column(db.String(36))
    reviewed_at = db.Column(db.DateTime(timezone=True))
    rejection_reason = db.Column(db.Text)

    created_at = db.Column(db.DateTime(timezone=True), default=now)
    updated_at = db.Column(db.DateTime(timezone=True), default=now, onupdate=now)

    manager = db.relationship("User", backref="organization", uselist=False, primaryjoin="and_(User.organization_id==Organization.id, User.role=='MANAGER')", foreign_keys="User.organization_id")


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=uid)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"))

    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    job_title = db.Column(db.String(100))
    phone = db.Column(db.String(30))

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password = db.Column(db.Text)

    role = db.Column(db.String(30), nullable=False)

    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    email_verified_at = db.Column(db.DateTime(timezone=True))

    account_status = db.Column(db.String(20), nullable=False, default="ACTIVE")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    avatar_url = db.Column(db.Text)

    created_at = db.Column(db.DateTime(timezone=True), default=now)
    updated_at = db.Column(db.DateTime(timezone=True), default=now, onupdate=now)

    def to_dict(self, include_org=False):
        data = {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "role": self.role,
            "job_title": self.job_title,
            "phone": self.phone,
            "avatar_url": self.avatar_url,
            "email_verified": self.email_verified,
            "account_status": self.account_status,
            "is_active": self.is_active,
            "organization_id": self.organization_id,
        }
        if include_org and self.organization:
            data["organization"] = {
                "id": self.organization.id,
                "name": self.organization.name,
                "city": self.organization.city,
                "country": self.organization.country,
                "status": self.organization.status,
            }
        return data


class EmailVerificationCode(db.Model):
    __tablename__ = "email_verification_codes"

    id = db.Column(db.String(36), primary_key=True, default=uid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    purpose = db.Column(db.String(30), nullable=False, default="REGISTER")
    code = db.Column(db.String(10), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    verified_at = db.Column(db.DateTime(timezone=True))
    attempts = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=now)


class AccountInvitation(db.Model):
    __tablename__ = "account_invitations"

    id = db.Column(db.String(36), primary_key=True, default=uid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    token = db.Column(db.String(255), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=now)


class OrganizationDocument(db.Model):
    __tablename__ = "organization_documents"

    id = db.Column(db.String(36), primary_key=True, default=uid)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False)
    document_type = db.Column(db.String(50), nullable=False)
    file_url = db.Column(db.Text, nullable=False)
    uploaded_at = db.Column(db.DateTime(timezone=True), default=now)


class Tracker(db.Model):
    __tablename__ = "trackers"

    id = db.Column(db.String(36), primary_key=True, default=uid)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False)
    device_id = db.Column(db.String(100), unique=True, nullable=False)
    msisdn = db.Column(db.String(30))
    vehicle_registration = db.Column(db.String(30))
    status = db.Column(db.String(30), nullable=False, default="ACTIVE")
    last_seen_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=now)
    updated_at = db.Column(db.DateTime(timezone=True), default=now, onupdate=now)


class Cargo(db.Model):
    __tablename__ = "cargos"

    id = db.Column(db.String(36), primary_key=True, default=uid)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False)
    tracker_id = db.Column(db.String(36), db.ForeignKey("trackers.id"))
    reference = db.Column(db.String(100), unique=True, nullable=False)
    type = db.Column(db.String(50), nullable=False)
    criticality = db.Column(db.String(20), nullable=False, default="MEDIUM")
    status = db.Column(db.String(30), nullable=False, default="PENDING")

    origin = db.Column(db.String(150), nullable=False)
    destination = db.Column(db.String(150), nullable=False)
    origin_lat = db.Column(db.Float, nullable=False)
    origin_lng = db.Column(db.Float, nullable=False)
    destination_lat = db.Column(db.Float, nullable=False)
    destination_lng = db.Column(db.Float, nullable=False)

    departed_at = db.Column(db.DateTime(timezone=True))
    speed_kmh = db.Column(db.Float, default=70)
    deadline = db.Column(db.DateTime(timezone=True))

    assigned_driver_id = db.Column(db.String(36), db.ForeignKey("users.id"))

    created_at = db.Column(db.DateTime(timezone=True), default=now)
    updated_at = db.Column(db.DateTime(timezone=True), default=now, onupdate=now)

    tracker = db.relationship("Tracker", backref="cargos")
    driver = db.relationship("User", backref="cargos", foreign_keys=[assigned_driver_id])


class TrackerLocation(db.Model):
    __tablename__ = "tracker_locations"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    tracker_id = db.Column(db.String(36), db.ForeignKey("trackers.id"), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    accuracy = db.Column(db.Float)
    source = db.Column(db.String(30), nullable=False, default="GPS")
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False, default=now)

    tracker = db.relationship("Tracker", backref="locations")


class Alert(db.Model):
    __tablename__ = "alerts"

    id = db.Column(db.String(36), primary_key=True, default=uid)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False)
    cargo_id = db.Column(db.String(36), db.ForeignKey("cargos.id"))
    tracker_id = db.Column(db.String(36), db.ForeignKey("trackers.id"))
    severity = db.Column(db.String(20), nullable=False, default="MEDIUM")
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="OPEN")
    created_at = db.Column(db.DateTime(timezone=True), default=now)
    acknowledged_at = db.Column(db.DateTime(timezone=True))
    acknowledged_by = db.Column(db.String(36))

    cargo = db.relationship("Cargo", backref="alerts")

    def to_dict(self):
        return {
            "id": self.id,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "cargo_reference": self.cargo.reference if self.cargo else None,
            "cargo_id": self.cargo_id,
        }


class Corridor(db.Model):
    __tablename__ = "corridors"

    id = db.Column(db.String(36), primary_key=True, default=uid)
    name = db.Column(db.String(150), nullable=False)
    origin = db.Column(db.String(150), nullable=False)
    destination = db.Column(db.String(150), nullable=False)
    points_json = db.Column(db.Text, nullable=False, default="[]")
    risk_level = db.Column(db.String(20), nullable=False, default="LOW")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=now)


class RiskZone(db.Model):
    __tablename__ = "risk_zones"

    id = db.Column(db.String(36), primary_key=True, default=uid)
    name = db.Column(db.String(150), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    risk_level = db.Column(db.String(20), nullable=False)
    points_json = db.Column(db.Text, nullable=False, default="[]")
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=now)
 
 
class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.String(36), primary_key=True, default=uid)
    actor_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    actor_email = db.Column(db.String(255))
    action = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.String(100))
    ip_address = db.Column(db.String(50))
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=now)

    def to_dict(self):
        return {
            "id": self.id,
            "actor_id": self.actor_id,
            "actor_email": self.actor_email,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "ip_address": self.ip_address,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }