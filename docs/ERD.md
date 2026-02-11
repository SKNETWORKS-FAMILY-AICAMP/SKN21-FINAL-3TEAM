# WorkFlow Agent — ERD (Entity Relationship Diagram)

> 11개 테이블 | PostgreSQL 16 | Alembic 마이그레이션 적용 완료

```mermaid
erDiagram
    users {
        int id PK
        varchar(255) email UK
        varchar(255) hashed_password
        varchar(100) name
        boolean is_admin
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    documents {
        int id PK
        varchar(500) title
        varchar(1000) file_path
        varchar(20) file_type
        text content "nullable"
        varchar(10) scope "company / personal"
        int uploaded_by FK
        varchar(20) status "processing / ready / error"
        datetime created_at
        datetime updated_at
    }

    document_templates {
        int id PK
        varchar(500) name
        text description "nullable"
        varchar(1000) file_path "nullable"
        varchar(20) file_type "nullable"
        text parsed_structure "nullable, JSON"
        varchar(50) category "meeting_minutes / report / jd / proposal / custom"
        boolean is_system
        varchar(10) scope "company / personal"
        int uploaded_by FK "nullable"
        varchar(20) status "processing / ready / error"
        datetime created_at
        datetime updated_at
    }

    regulations {
        int id PK
        varchar(500) title
        varchar(100) category
        varchar(50) article_number
        text content
        varchar(20) version
        datetime created_at
        datetime updated_at
    }

    meetings {
        int id PK
        varchar(500) title
        text raw_content
        text summary "nullable"
        text decisions "nullable, JSON"
        varchar(20) risk_level "nullable"
        datetime meeting_date "nullable"
        int created_by FK
        datetime created_at
        datetime updated_at
    }

    action_items {
        int id PK
        int meeting_id FK
        varchar(1000) content
        varchar(100) assignee "nullable"
        datetime due_date "nullable"
        varchar(20) priority "high / medium / low"
        varchar(20) status "pending / in_progress / done"
        varchar(255) google_task_id "nullable"
        int sheet_row_id "nullable"
        datetime email_sent_at "nullable"
        datetime created_at
        datetime updated_at
    }

    schedules {
        int id PK
        varchar(500) title
        varchar(2000) description "nullable"
        datetime start_time
        datetime end_time "nullable"
        varchar(50) schedule_type "meeting / task / deadline"
        varchar(20) priority
        varchar(255) google_event_id "nullable"
        varchar(500) google_meet_link "nullable"
        int action_item_id FK "nullable"
        int user_id FK
        datetime created_at
        datetime updated_at
    }

    judgments {
        int id PK
        text question
        varchar(30) result "yes / no / conditional / no_regulation"
        float confidence
        text reasoning
        text conditions "nullable"
        text alternatives "nullable"
        text regulations_cited "JSON"
        int user_id FK
        datetime created_at
        datetime updated_at
    }

    chat_logs {
        int id PK
        int user_id FK
        text user_message
        varchar(50) intent
        float intent_confidence
        varchar(50) agent_type "judgment / document / schedule"
        text agent_response
        int response_time_ms "nullable"
        datetime created_at
        datetime updated_at
    }

    oauth_tokens {
        int id PK
        int user_id FK "unique"
        varchar(50) provider
        text access_token
        text refresh_token "nullable"
        datetime expires_at "nullable"
        text scopes "nullable"
        datetime created_at
        datetime updated_at
    }

    google_sheet_trackers {
        int id PK
        int user_id FK
        varchar(255) spreadsheet_id
        varchar(500) spreadsheet_url
        varchar(255) sheet_name
        int meeting_id FK "nullable"
        datetime created_at
        datetime updated_at
    }

    %% Relationships
    users ||--o{ documents : "uploads"
    users ||--o{ document_templates : "uploads"
    users ||--o{ meetings : "creates"
    users ||--o{ schedules : "owns"
    users ||--o{ judgments : "requests"
    users ||--o{ chat_logs : "chats"
    users ||--o| oauth_tokens : "authenticates"
    users ||--o{ google_sheet_trackers : "tracks"

    meetings ||--o{ action_items : "has"
    meetings ||--o{ google_sheet_trackers : "tracked_by"

    action_items ||--o| schedules : "linked_to"
```

## 테이블 관계 요약

| FK | From | To | 관계 |
|----|------|----|------|
| `documents.uploaded_by` | documents | users | N:1 |
| `document_templates.uploaded_by` | document_templates | users | N:1 (nullable) |
| `meetings.created_by` | meetings | users | N:1 |
| `action_items.meeting_id` | action_items | meetings | N:1 |
| `schedules.user_id` | schedules | users | N:1 |
| `schedules.action_item_id` | schedules | action_items | N:1 (nullable) |
| `judgments.user_id` | judgments | users | N:1 |
| `chat_logs.user_id` | chat_logs | users | N:1 |
| `oauth_tokens.user_id` | oauth_tokens | users | 1:1 |
| `google_sheet_trackers.user_id` | google_sheet_trackers | users | N:1 |
| `google_sheet_trackers.meeting_id` | google_sheet_trackers | meetings | N:1 (nullable) |

## 독립 테이블

| 테이블 | 설명 |
|--------|------|
| `regulations` | FK 없음 — RAG 검색 대상, 별도 임베딩 |
