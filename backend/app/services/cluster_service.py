import logging
import re
import math
from collections import Counter
from datetime import datetime
from sqlalchemy.orm import Session
from app.database.models.ticket import Ticket
from app.database.models.workflow_models import IncidentCluster

logger = logging.getLogger("it-agent-backend")

def compute_cosine_similarity(text1: str, text2: str) -> float:
    """
    Computes a self-contained token-based cosine similarity between two text strings.
    """
    if not text1 or not text2:
        return 0.0

    words1 = re.findall(r'\w+', text1.lower())
    words2 = re.findall(r'\w+', text2.lower())

    if not words1 or not words2:
        return 0.0

    counter1 = Counter(words1)
    counter2 = Counter(words2)

    intersection = set(counter1.keys()) & set(counter2.keys())
    numerator = sum(counter1[x] * counter2[x] for x in intersection)

    sum1 = sum(counter1[x] ** 2 for x in counter1.keys())
    sum2 = sum(counter2[x] ** 2 for x in counter2.keys())
    denominator = math.sqrt(sum1) * math.sqrt(sum2)

    if not denominator:
        return 0.0
    return numerator / denominator

class ClusterService:
    @staticmethod
    def cluster_ticket(db: Session, ticket: Ticket, threshold: float = 0.6) -> int | None:
        """
        Scans existing tickets to cluster the new ticket if similarity exceeds the threshold.
        """
        ticket_desc = ticket.description or ticket.issue_description or ""
        if not ticket_desc:
            return None

        # Fetch other tickets
        other_tickets = db.query(Ticket).filter(Ticket.id != ticket.id).all()
        
        best_similarity = 0.0
        best_match = None

        for other in other_tickets:
            other_desc = other.description or other.issue_description or ""
            sim = compute_cosine_similarity(ticket_desc, other_desc)
            if sim > best_similarity:
                best_similarity = sim
                best_match = other

        if best_similarity >= threshold and best_match:
            logger.info(
                "Cluster Match: Ticket %s matches ticket %s with similarity %.2f (threshold %.2f)",
                ticket.ticket_id, best_match.ticket_id, best_similarity, threshold
            )
            # If the matching ticket is already in a cluster, join that cluster
            if best_match.cluster_id:
                ticket.cluster_id = best_match.cluster_id
                return best_match.cluster_id
            else:
                # Create a new cluster and add both tickets to it
                cluster_name = f"Cluster - {ticket.category} - {best_match.ticket_id}"
                # Ensure cluster name is unique
                existing_cluster = db.query(IncidentCluster).filter(IncidentCluster.name == cluster_name).first()
                if existing_cluster:
                    cluster = existing_cluster
                else:
                    cluster = IncidentCluster(
                        name=cluster_name,
                        known_fix=None,
                        created_at=datetime.utcnow()
                    )
                    db.add(cluster)
                    db.flush()
                
                best_match.cluster_id = cluster.id
                ticket.cluster_id = cluster.id
                return cluster.id

        return None

    @staticmethod
    def get_clusters_dashboard(db: Session) -> list:
        """
        Returns details for all clusters, including incident counts, MTTR, and affected users.
        """
        clusters = db.query(IncidentCluster).all()
        result = []

        for cluster in clusters:
            tickets = db.query(Ticket).filter(Ticket.cluster_id == cluster.id).all()
            if not tickets:
                continue

            open_count = sum(1 for t in tickets if t.status not in ("RESOLVED", "CLOSED"))
            resolved_count = sum(1 for t in tickets if t.status in ("RESOLVED", "CLOSED"))
            affected_users = list(set(t.created_by for t in tickets if t.created_by))
            
            # Compute MTTR for resolved/closed tickets in this cluster
            resolution_times = []
            for t in tickets:
                if t.resolved_at and t.created_at:
                    resolution_times.append((t.resolved_at - t.created_at).total_seconds())
                elif t.closed_at and t.created_at:
                    resolution_times.append((t.closed_at - t.created_at).total_seconds())

            avg_mttr_sec = sum(resolution_times) / len(resolution_times) if resolution_times else 0.0
            
            result.append({
                "id": cluster.id,
                "name": cluster.name,
                "known_fix": cluster.known_fix,
                "created_at": cluster.created_at,
                "open_count": open_count,
                "resolved_count": resolved_count,
                "total_count": len(tickets),
                "affected_users": affected_users,
                "avg_mttr_sec": avg_mttr_sec,
                "tickets": [
                    {
                        "ticket_id": t.ticket_id,
                        "status": t.status,
                        "created_by": t.created_by,
                        "priority": t.priority,
                        "created_at": t.created_at
                    } for t in tickets
                ]
            })
            
        return result

    @staticmethod
    def update_known_fix(db: Session, cluster_id: int, known_fix: str) -> bool:
        """
        Updates the known resolution fix for a specific incident cluster.
        """
        cluster = db.query(IncidentCluster).filter(IncidentCluster.id == cluster_id).first()
        if cluster:
            cluster.known_fix = known_fix
            db.commit()
            return True
        return False
