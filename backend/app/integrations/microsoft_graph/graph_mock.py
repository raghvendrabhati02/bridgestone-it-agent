import logging

logger = logging.getLogger("it-agent-backend")

class MicrosoftGraphMock:
    def __init__(self):
        # Seed initial mock data
        self.users = {
            "graph-user-12345": {
                "id": "graph-user-12345",
                "displayName": "Test Employee",
                "mail": "employee@bridgestone.com",
                "userPrincipalName": "employee@bridgestone.com",
                "jobTitle": "IT Engineer",
                "officeLocation": "Building A, Floor 2"
            },
            "graph-user-manager": {
                "id": "graph-user-manager",
                "displayName": "Test Manager",
                "mail": "manager@bridgestone.com",
                "userPrincipalName": "manager@bridgestone.com",
                "jobTitle": "IT Manager",
                "officeLocation": "Building A, Floor 3"
            }
        }
        
        self.managers = {
            "graph-user-12345": "graph-user-manager"
        }
        
        self.user_groups = {
            "graph-user-12345": [
                {"id": "grp-1", "displayName": "Domain Users", "description": "Standard domain users"},
                {"id": "grp-2", "displayName": "VPN Users", "description": "Users allowed to connect to corporate VPN"}
            ],
            "graph-user-manager": [
                {"id": "grp-1", "displayName": "Domain Users", "description": "Standard domain users"},
                {"id": "grp-3", "displayName": "Domain Admins", "description": "Admins"}
            ]
        }
        
        self.group_members = {
            "grp-1": ["graph-user-12345", "graph-user-manager"],
            "grp-2": ["graph-user-12345"],
            "grp-3": ["graph-user-manager"]
        }
        
        self.mailboxes = {
            "graph-user-12345": {
                "mailbox_status": "ACTIVE",
                "exchange_server": "ONLINE",
                "exchange_latency": 18,
                "settings": {
                    "automaticRepliesSetting": {"status": "disabled"},
                    "timeZone": "UTC",
                    "language": {"locale": "en-US"}
                }
            },
            "graph-user-manager": {
                "mailbox_status": "ACTIVE",
                "exchange_server": "ONLINE",
                "exchange_latency": 20,
                "settings": {
                    "automaticRepliesSetting": {"status": "disabled"},
                    "timeZone": "UTC",
                    "language": {"locale": "en-US"}
                }
            }
        }
        
        self.licenses = {
            "graph-user-12345": [
                {
                    "skuId": "c7ad517e-7c09-42b0-844d-d18309f68590",
                    "skuPartNumber": "ENTERPRISEPACK",  # Office 365 E3
                    "capabilityStatus": "Enabled"
                }
            ],
            "graph-user-manager": [
                {
                    "skuId": "06371584-c816-4af5-bc91-ae0e2d6349c2",
                    "skuPartNumber": "SPE_E5",  # Microsoft 365 E5
                    "capabilityStatus": "Enabled"
                }
            ]
        }

    def get_user(self, user_id: str) -> dict | None:
        # Try lookup by ID or UPN/Email
        if user_id in self.users:
            return self.users[user_id]
        for u in self.users.values():
            if u["userPrincipalName"] == user_id or u["mail"] == user_id:
                return u
        return None

    def get_user_profile(self, user_id: str) -> dict | None:
        return self.get_user(user_id)

    def get_manager(self, user_id: str) -> dict | None:
        user = self.get_user(user_id)
        if not user:
            return None
        manager_id = self.managers.get(user["id"])
        if manager_id:
            return self.users.get(manager_id)
        return None

    def get_user_groups(self, user_id: str) -> list:
        user = self.get_user(user_id)
        if not user:
            return []
        return self.user_groups.get(user["id"], [])

    def get_mailbox_status(self, user_id: str) -> dict | None:
        user = self.get_user(user_id)
        if not user:
            return None
        mb = self.mailboxes.get(user["id"])
        if mb:
            return {
                "mailbox_status": mb["mailbox_status"],
                "exchange_server": mb["exchange_server"],
                "exchange_latency": mb["exchange_latency"]
            }
        return None

    def get_mailbox_settings(self, user_id: str) -> dict | None:
        user = self.get_user(user_id)
        if not user:
            return None
        mb = self.mailboxes.get(user["id"])
        if mb:
            return mb.get("settings", {})
        return None

    def get_assigned_licenses(self, user_id: str) -> list:
        user = self.get_user(user_id)
        if not user:
            return []
        return self.licenses.get(user["id"], [])

    def get_group_membership(self, group_id: str) -> list:
        member_ids = self.group_members.get(group_id, [])
        return [self.users[mid] for mid in member_ids if mid in self.users]

    def get_all_users(self) -> list:
        return list(self.users.values())

    def get_all_groups(self) -> list:
        seen = set()
        unique_groups = []
        for groups in self.user_groups.values():
            for g in groups:
                if g["id"] not in seen:
                    seen.add(g["id"])
                    unique_groups.append(g)
        return unique_groups

    def add_user(self, user_data: dict):
        self.users[user_data["id"]] = user_data

    def add_user_to_group(self, user_id: str, group_id: str, group_name: str):
        user = self.get_user(user_id)
        if not user:
            return
        uid = user["id"]
        # Ensure group in user_groups
        if uid not in self.user_groups:
            self.user_groups[uid] = []
        if not any(g["id"] == group_id for g in self.user_groups[uid]):
            self.user_groups[uid].append({"id": group_id, "displayName": group_name})
        # Ensure user in group_members
        if group_id not in self.group_members:
            self.group_members[group_id] = []
        if uid not in self.group_members[group_id]:
            self.group_members[group_id].append(uid)

# Singleton mock database instance
microsoft_graph_mock_db = MicrosoftGraphMock()
