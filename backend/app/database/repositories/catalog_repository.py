from sqlalchemy.orm import Session
from app.database.models.service_catalog import ServiceCatalogItem

class CatalogRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_item(self, service_id: str) -> ServiceCatalogItem | None:
        return self.db.query(ServiceCatalogItem).filter(ServiceCatalogItem.service_id == service_id).first()

    def get_all_items(self) -> list[ServiceCatalogItem]:
        return self.db.query(ServiceCatalogItem).filter(ServiceCatalogItem.status == "ACTIVE").all()

    def create_item(self, **kwargs) -> ServiceCatalogItem:
        item = ServiceCatalogItem(**kwargs)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item
