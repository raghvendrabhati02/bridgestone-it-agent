from sqlalchemy.orm import Session
from app.database.models.service_request import ServiceRequest
from datetime import datetime

class RequestRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_request(self, request_id: str) -> ServiceRequest | None:
        return self.db.query(ServiceRequest).filter(ServiceRequest.request_id == request_id).first()

    def get_all_requests(self) -> list[ServiceRequest]:
        return self.db.query(ServiceRequest).order_by(ServiceRequest.created_at.desc()).all()

    def get_requests_by_user(self, username: str) -> list[ServiceRequest]:
        return self.db.query(ServiceRequest).filter(ServiceRequest.requested_by == username).order_by(ServiceRequest.created_at.desc()).all()

    def create_request(self, **kwargs) -> ServiceRequest:
        request = ServiceRequest(**kwargs)
        if not request.created_at:
            request.created_at = datetime.utcnow()
        if not request.updated_at:
            request.updated_at = datetime.utcnow()
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)
        return request

    def update_request(self, request_id: str, **kwargs) -> ServiceRequest | None:
        request = self.get_request(request_id)
        if not request:
            return None
        for key, value in kwargs.items():
            if hasattr(request, key):
                setattr(request, key, value)
        request.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(request)
        return request
