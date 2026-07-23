# ServiceNow Field Mapping Configuration

This directory holds the official **ServiceNow Export Mapping Files** (Excel `.xlsx` or CSV `.csv`) used by the IT Agent `FieldMappingService`.

> **IMPORTANT**: The application **never** generates or overwrites mapping files automatically. Real ServiceNow export files provided by ServiceNow administrators must be placed in this folder.

---

## 📁 Directory Structure

```text
backend/app/data/servicenow_mappings/
├── README.md                          # This documentation file
├── sys_choice_mappings.xlsx           # Exported Choice Table mappings (sys_choice)
└── assignment_groups.xlsx             # Exported Assignment Group mappings (sys_user_group)
```

---

## ⚙️ Environment Variables & Configuration

The mapping directory and file names are fully configurable via environment variables or service parameters:

| Environment Variable | Default Value | Description |
| :--- | :--- | :--- |
| `SERVICENOW_MAPPINGS_DIR` | `backend/app/data/servicenow_mappings` | Directory path containing export files |
| `SERVICENOW_CHOICE_MAPPINGS_FILE` | `sys_choice_mappings.xlsx` | Choice mappings filename |
| `SERVICENOW_GROUPS_MAPPINGS_FILE` | `assignment_groups.xlsx` | Assignment groups / Reference filename |

---

## 📋 Required Choice Table Format (`sys_choice`)

The choice mappings file (e.g. `sys_choice_mappings.xlsx`) must contain an export of ServiceNow's `sys_choice` table or equivalent choice mappings.

### **Required Columns**
The loader enforces strict validation on startup and will **fail fast** if any of the following mandatory columns are missing:

1. **`Element`**: ServiceNow field name (e.g., `u_type`, `category`, `subcategory`, `contact_type`).
2. **`Label`**: User-friendly label displayed in ServiceNow UI (e.g., `"Software Issue"`, `"VPN Access"`).
3. **`Value`**: Authoritative API value used in payload generation (e.g., `"software"`, `"vpn"`).
4. **`Dependent Value`**: Parent value used for dependent choice lists (e.g., `u_type` value for a category, `category` value for a subcategory).

> **Note**: Column headers are case-insensitive and allow standard variations (e.g. `Dependent_Value` or `Dependent Value`).

### **Example `sys_choice` Table**

| Table | Element | Label | Value | Dependent Value |
| :--- | :--- | :--- | :--- | :--- |
| incident | u_type | Issue | issue | |
| incident | u_type | Service Request | request | |
| incident | category | Hardware | hardware | issue |
| incident | category | Software | software | issue |
| incident | category | VPN | vpn | issue |
| incident | category | Software Access | software_access | request |
| incident | subcategory | GlobalProtect | globalprotect | vpn |
| incident | subcategory | Cisco AnyConnect | cisco_vpn | vpn |
| incident | subcategory | Outlook Crashing | outlook_crash | software |
| incident | contact_type | Chat | chat | |

---

## 👥 Required Reference / Assignment Group Format (`sys_user_group`)

Assignment groups and reference fields are supported via choice or reference mapping loaders.

### **Supported Columns**
- `Name` or `Group Name` or `Label`: Human readable group name (e.g. `"Network Team"`).
- `Value` or `Sys ID`: API reference value or sys_id.

### **Example Assignment Group Table**

| Group Name | Value | Category |
| :--- | :--- | :--- |
| Network Team | Network Team | VPN |
| IT Support | IT Support | GENERAL |
| Identity Team | Identity Team | PASSWORD_RESET |

---

## 🔗 Dependency Rules

1. **Category Dependency**: `category` choices depend on `u_type` using the `Dependent Value` column.
   - Example: Category `"vpn"` has `Dependent Value = "issue"`. It is only valid when `u_type` is `"issue"`.
2. **Subcategory Dependency**: `subcategory` choices depend on `category` using the `Dependent Value` column.
   - Example: Subcategory `"globalprotect"` has `Dependent Value = "vpn"`. It is only valid when `category` is `"vpn"`.
3. **Payload Resolution**: The engine resolves user input Labels to authoritative API `Value` strings. The `Label` is **never** sent in API payloads.

---

## ⚡ Performance & Caching

Excel files are read and validated **once** when `FieldMappingService` initializes or when `load_mappings()` is explicitly called. All mapping lookups and payload builds run against in-memory data structures for high performance and zero disk I/O per incident creation.
