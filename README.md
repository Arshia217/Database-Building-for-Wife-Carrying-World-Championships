# Database-Building-for-Wife-Carrying-World-Championships
Part of project under the course Data and Applications.

# Wife Carrying World Championships (Eukonkanto): Database and Web App

**Team 20 (Team Tangled)** | Course: Data and Applications | Project Phase 4

Mini World: the Wife Carrying World Championships, Sonkajärvi, Finland (https://eukonkanto.fi).

## 1. Paradigm and stack

- **Paradigm:** Relational. **DBMS:** MySQL 8.0 / MariaDB 11.8 (InnoDB engine).
- **Backend:** Python 3 with Flask and PyMySQL (strictly raw, parameterized SQL; no ORM used).
- **Frontend:** Server-rendered Jinja2 templates styled with custom, responsive HTML/CSS.
- **Application Structure:**
  - `src/db.py`: Database connection pool and transaction manager (`transaction()` context manager, raw query executors).
  - `src/services.py`: Data access service layer implementing the 5 read queries, 3 write operations, and administrator credential verification (`authenticate_admin`).
  - `src/app.py`: Flask application routing, session management, role-based access control decorator (`@admin_required`), form handling, flash notifications, and template rendering.
  - `src/templates/`: Jinja2 templates (`base.html`, `index.html`, `entries.html`, `search.html`, `categories.html`, `results.html`, `register_pair.html`, `edit_participant.html`, `manage_entries.html`, `login.html`).
  - `src/static/style.css`: Clean, modern stylesheet.

## 2. Design Changes

Teams that worked on this Mini World: **Phase 2: Team 16**, **Phase 3: Team 7**.
Baseline is the Team 7 Phase 3 schema (3NF). Significant changes:

| # | Change | Reason |
|---|---|---|
| R1 | `edition_year` restored in `RECORDS_RESULT` and `ASSIGNED_TO` (not part of the primary key), with composite foreign keys to `COMPETITION_ENTRY(entry_id, edition_year)` and `HEAT`. `WINS` also uses a composite foreign key. `COMPETITION_ENTRY` gets `UNIQUE(entry_id, edition_year)`. | Phase 3 removed the column and needed a trigger to check heat existence. Now MySQL enforces it natively, and an entry can only win in its own edition. |
| R2 | `COMPETITION_ENTRY` and `RACE` reference `HAS_CATEGORY(edition_year, category_id)`. | An entry or race may only use a category that the edition offers (R2 relationship). |
| R3 | `participant.date_of_birth` may be NULL. | Not published on the website. |
| R4 | `participant.last_name` may be NULL. | The website sometimes shows only a first name (5 people). |
| R5 | `competition_entry.bib_number` may be NULL. | Bibs of the 2024 and 2025 winners are not published. |
| R6 | `records_result.official_id` may be NULL. | The website does not say who recorded each time. `result_correction_log.official_id` stays NOT NULL. |
| R7 | `records_result.recording_timestamp` may be NULL. | Not published for imported results. |
| R8 | `pair_entry` carrier/carried foreign keys use `ON UPDATE RESTRICT`. | MySQL does not allow a CHECK on a column with a CASCADE rule (error 3823); participant ids never change. |
| R9 | Added triggers: race date must lie inside the edition's dates (rule 7); an entry cannot be both a pair and a team (disjoint specialization). | Cannot be declared as plain constraints. |
| R10 | `participant.approval_status` column added (`ENUM('Pending', 'Approved', 'None') NOT NULL DEFAULT 'Approved'`). | Tracks whether each participant's entry is currently pending review, approved, or unassigned. Historical racers default to `'Approved'`. |
| R11 | Added table `admin_user(admin_id, username, password_hash, full_name, created_at)`. | Stores official administrator credentials with secure password hashing for administrator login and privileged operations. |

Unchanged from Phase 3: all relations, primary keys, `PAIR_ENTRY.carrier_id/carried_id`, and the weak entities `RACE` and `HEAT`. Column types, sizes and enum values follow the Phase 1 document. The reserved word `rank` is written with backticks. R3 to R7 follow the Phase 1 assumption that attributes the data cannot provide may be NULL.

## 3. Data

All data comes from the website (results, categories and rules, winners, edition dates). **Nothing is invented.**

- **2026:** Full results, 87 entries including 2024/2025 winners, 86 results in 8 heats (Friday sprint: 3 heats + final; Saturday: Team, Women, 40+, Main Series).
- **2024 and 2025:** Gold medalists only (the site gives no heat-level results for earlier years).
- **2027:** Scheduled edition (2-3 July 2027) with the Main Series, Sprint and Team Series categories, so new registrations can be made.
- Not loaded because the site does not publish them: officials, dates of birth, weights, contact numbers.

**Interpretations (not data errors):**
- When the website lists two countries for one pair or team, they were matched to the names in order.
- The 15 s penalty of *Team 2 SPOLK* is treated as included in the listed time (`raw_time = listed time - 15`).
- Names shown with one word only (Francois, Mathilde, Svetlana, Vaimo, Sanna) have no last name.
- The sprint is modelled as race 1 (heats 1-3) and race 2 (final). Saturday series are races 3-6 with one heat each.
- Category `minimum_age` (17) applies to the carried person; the 40+ rule "carrier must be 40 or older" is in the rules text and is checked by the application.
- Only 2026 has heat-level data, so cross-edition time comparisons only cover 2026.

## 4. Setup and run

### Automated Setup
To grant database privileges, initialize the schema, populate the dataset, and test connectivity:
```bash
./scripts/setup_database.sh
```

### Manual Setup
1. **Initialize Database and Permissions:**
   ```bash
   sudo mariadb < scripts/setup_access.sql     # or: mysql -u root -p < scripts/setup_access.sql
   mariadb -u eukakanto_user -peukakanto_pass < src/schema.sql
   mariadb -u eukakanto_user -peukakanto_pass < src/populate.sql
   ```
2. **Environment Configuration:**
   Create a `.env` file (copied from `.env.example`):
   ```ini
   DB_HOST=127.0.0.1
   DB_PORT=3306
   DB_USER=eukakanto_user
   DB_PASS=eukakanto_pass
   DB_NAME=eukakanto
   ```
3. **Install Dependencies & Start the Application:**
   - **Using `uv`:**
     ```bash
     uv add -r requirements.txt
     uv run python src/app.py
     ```
   - **Using standard `pip`:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     pip install -r requirements.txt
     python src/app.py
     ```
   Open [http://localhost:5000](http://localhost:5000) in your web browser.

## 5. Functional Requirements Implementation (Section 4.3)

According to **Section 4.3 (Functional Requirements Implementation)**, the web application must implement at least **five distinct query (read) operations** and **three distinct update (write) operations** (including at least one create, one update, and one delete). 

Below is the mapping for our relational implementation (**MySQL 8.0 / MariaDB 11.8** using raw parameterized SQL):

### 5.1 Access Control & User Roles (Public vs. Administrator)

The application implements strict Role-Based Access Control (RBAC) separating public visitors from authorized race administrators:

- **Public Users (Unauthenticated):**
  - **Read Access:** Full access to all 5 read queries (Approved Entries, Competitor Name Search, Category Breakdown, Heat Results, Category Averages).
  - **Write Access:** Solely allowed access to the pair registration page (`/register`). Upon form submission, the entry is automatically inserted with status **`Pending` by default**; regular users have **no option to choose status**.
  - Protected administrative write routes redirect unauthenticated users to `/login` with an informative warning.
- **Race Administrators (Authenticated):**
  - **Authentication:** Dedicated login portal (`/login`) verifying credentials against the `admin_user` database table (Default admin: `admin` / `admin123`).
  - **Read Access:** Unrestricted access to all read queries.
  - **Write Access:** Full access to all administrative write operations:
    - **W1 (Create):** Register pairs with optional administrative pre-approval.
    - **W2 (Update):** Change participant nationality representation (`/participants/update-country`).
    - **W3 (Delete & Approval):** Review pending registrations, approve confirmed entrants (`/entries/approve/<id>`), and delete unapproved entries with automatic orphan cleanup (`/entries/delete/<id>`).

### 5.2 Requirements Compliance Summary

| Operation Type | SQL Keyword | Requirement Mapping | Feature Name | Page / URL | Access Level | Implementation Method / Query Technique |
|---|---|---|---|---|---|---|
| **Query (Read 1)** | `SELECT` | Read Operation 1 | **Approved Entries per Edition** | `/entries` | Public & Admin | Multi-table `JOIN` & `LEFT JOIN`, `CONCAT_WS`, parameterized filtering by edition and category |
| **Query (Read 2)** | `SELECT` | Read Operation 2 | **Participant Name Search** | `/search` | Public & Admin | Full/partial name wildcard search (`LIKE %s`) joining participant history, category, and approval status |
| **Query (Read 3)** | `SELECT` | Read Operation 3 | **Entries per Category Breakdown** | `/categories` | Public & Admin | Aggregation query with `COUNT(entry_id)` and conditional sums (`SUM(CASE WHEN ...) GROUP BY`) |
| **Query (Read 4)** | `SELECT` | Read Operation 4 | **Heat Result Sheet & Delta** | `/results` | Public & Admin | Window function `MIN(...) OVER ()` to compute time difference from heat winner (`time_diff`) |
| **Query (Read 5)** | `SELECT` | Read Operation 5 | **Average Final Time Analysis** | `/categories#averages` | Public & Admin | Statistical aggregation (`AVG`, `MIN`, `MAX`, `COUNT`) grouped by category |
| **Write (Create)** | `INSERT` | Write Operation 1 | **Register a Pair Entry** | `/register` | Public (Pending) & Admin | Text input competitor insertion into `participant` (with `approval_status`), master entry, subtype, and edition linking |
| **Write (Update)** | `UPDATE` | Write Operation 2 | **Change Participant Country** | `/participants/update-country` | Admin Only | Parameterized `UPDATE participant SET country_code = %s` with foreign key verification |
| **Write (Delete)** | `DELETE` | Write Operation 3 | **Delete Pending Entry & Approval** | `/entries/manage` | Admin Only | Multi-table cascade `DELETE`, edition participation cleanup, orphaned competitor removal, and atomic approval |

---

### 5.3 Detailed Query (Read) Operations

#### **R1. Approved Entries per Edition**
- **URL / Route:** `/entries` (`GET`)
- **Backend Function:** `query_approved_entries(edition_year, category_id)` in `src/services.py`
- **Description:** Allows spectators and officials to browse confirmed entries for any selected championship edition (e.g. 2026) and optionally filter by category.
- **SQL Implementation:**
  ```sql
  SELECT 
      ce.entry_id, ce.bib_number, ce.edition_year, ce.registration_status, ce.registration_time,
      c.category_name, pe.carrier_id,
      CONCAT_WS(' ', p1.first_name, p1.last_name) AS carrier_name,
      co1.country_name AS carrier_country, pe.carried_id,
      CONCAT_WS(' ', p2.first_name, p2.last_name) AS carried_name,
      co2.country_name AS carried_country, te.team_name
  FROM competition_entry ce
  JOIN category c ON ce.category_id = c.category_id
  LEFT JOIN pair_entry pe ON ce.entry_id = pe.entry_id
  LEFT JOIN participant p1 ON pe.carrier_id = p1.participant_id
  LEFT JOIN country co1 ON p1.country_code = co1.country_code
  LEFT JOIN participant p2 ON pe.carried_id = p2.participant_id
  LEFT JOIN country co2 ON p2.country_code = co2.country_code
  LEFT JOIN team_entry te ON ce.entry_id = te.entry_id
  WHERE ce.edition_year = %s AND ce.registration_status = 'Approved' [AND ce.category_id = %s]
  ORDER BY ce.bib_number IS NULL, ce.bib_number, ce.entry_id;
  ```

#### **R2. Participant Name Search**
- **URL / Route:** `/search` (`GET`)
- **Backend Function:** `query_name_search(name_fragment)` in `src/services.py`
- **Description:** Enables search across the entire participant registry by partial or full name (e.g. "Taisto", "Katja"), retrieving their nationality, entered editions, categories, bib numbers, and designated roles (Carrier or Carried).
- **SQL Implementation:**
  ```sql
  SELECT 
      p.participant_id, CONCAT_WS(' ', p.first_name, p.last_name) AS full_name,
      p.first_name, p.last_name, p.approval_status, co.country_name,
      ce.entry_id, ce.edition_year, ce.bib_number, c.category_name,
      pi.participant_role, ce.registration_status
  FROM participant p
  JOIN country co ON p.country_code = co.country_code
  LEFT JOIN participates_in pi ON p.participant_id = pi.participant_id
  LEFT JOIN competition_entry ce ON pi.entry_id = ce.entry_id
  LEFT JOIN category c ON ce.category_id = c.category_id
  WHERE CONCAT_WS(' ', p.first_name, p.last_name) LIKE %s
  ORDER BY p.participant_id, ce.edition_year DESC;
  ```

#### **R3. Entries per Category Breakdown**
- **URL / Route:** `/categories` (`GET`)
- **Backend Function:** `query_entries_per_category(edition_year)` in `src/services.py`
- **Description:** Analytical breakdown summarizing the total registration volume across all categories for any championship year, detailing total applications, approved entries, and pending submissions.
- **SQL Implementation:**
  ```sql
  SELECT 
      hc.edition_year, c.category_id, c.category_name,
      COUNT(ce.entry_id) AS total_entries,
      COALESCE(SUM(CASE WHEN ce.registration_status = 'Approved' THEN 1 ELSE 0 END), 0) AS approved_entries,
      COALESCE(SUM(CASE WHEN ce.registration_status = 'Pending' THEN 1 ELSE 0 END), 0) AS pending_entries
  FROM has_category hc
  JOIN category c ON hc.category_id = c.category_id
  LEFT JOIN competition_entry ce 
      ON hc.edition_year = ce.edition_year AND hc.category_id = ce.category_id
  [WHERE hc.edition_year = %s]
  GROUP BY hc.edition_year, c.category_id, c.category_name
  ORDER BY hc.edition_year DESC, c.category_id;
  ```

#### **R4. Heat Result Sheet with Relative Time Differences**
- **URL / Route:** `/results` (`GET`)
- **Backend Function:** `query_heat_result_sheet(edition_year, race_no, heat_no)` in `src/services.py`
- **Description:** Official heat race sheet showing rank, bib, raw time, penalty seconds, computed final time (`raw_time + penalty_seconds`), and time difference behind the winner computed using SQL window functions. Nullable officials are cleanly preserved via `LEFT JOIN`.
- **SQL Implementation:**
  ```sql
  SELECT 
      rr.edition_year, rr.race_no, rr.heat_no, rr.`rank`, rr.result_status,
      ce.entry_id, ce.bib_number, te.team_name,
      CONCAT_WS(' ', p1.first_name, p1.last_name) AS carrier_name,
      CONCAT_WS(' ', p2.first_name, p2.last_name) AS carried_name,
      rr.raw_time, rr.penalty_seconds,
      CASE WHEN rr.result_status = 'Finished' THEN (rr.raw_time + rr.penalty_seconds) ELSE NULL END AS final_time,
      CASE 
          WHEN rr.result_status = 'Finished' THEN 
              ROUND((rr.raw_time + rr.penalty_seconds) - MIN(CASE WHEN rr.result_status = 'Finished' THEN (rr.raw_time + rr.penalty_seconds) END) OVER (), 3)
          ELSE NULL 
      END AS time_diff,
      CONCAT_WS(' ', o.first_name, o.last_name) AS official_name
  FROM records_result rr
  JOIN competition_entry ce ON rr.entry_id = ce.entry_id
  LEFT JOIN pair_entry pe ON ce.entry_id = pe.entry_id
  LEFT JOIN participant p1 ON pe.carrier_id = p1.participant_id
  LEFT JOIN participant p2 ON pe.carried_id = p2.participant_id
  LEFT JOIN team_entry te ON ce.entry_id = te.entry_id
  LEFT JOIN official o ON rr.official_id = o.official_id
  WHERE rr.edition_year = %s AND rr.race_no = %s AND rr.heat_no = %s
  ORDER BY 
      CASE WHEN rr.result_status = 'Finished' THEN 0 ELSE 1 END,
      rr.`rank` IS NULL, rr.`rank`, final_time;
  ```

#### **R5. Category Average Final Times Analysis**
- **URL / Route:** `/categories#averages` (`GET`)
- **Backend Function:** `query_average_final_times(edition_year)` in `src/services.py`
- **Description:** High-level statistical report aggregating finish times across competition categories, computing the number of finishers, average final time, fastest final time, and slowest final time.
- **SQL Implementation:**
  ```sql
  SELECT 
      c.category_id, c.category_name,
      COUNT(rr.entry_id) AS total_finishes,
      ROUND(AVG(rr.raw_time + rr.penalty_seconds), 3) AS avg_final_time,
      ROUND(MIN(rr.raw_time + rr.penalty_seconds), 3) AS fastest_final_time,
      ROUND(MAX(rr.raw_time + rr.penalty_seconds), 3) AS slowest_final_time
  FROM records_result rr
  JOIN competition_entry ce ON rr.entry_id = ce.entry_id
  JOIN category c ON ce.category_id = c.category_id
  WHERE rr.result_status = 'Finished' [AND rr.edition_year = %s]
  GROUP BY c.category_id, c.category_name
  ORDER BY avg_final_time ASC;
  ```

---

### 5.4 Detailed Update (Write) Operations

#### **W1. Register a Pair (Create Operation — `INSERT`)**
- **URL / Route:** `/register` (`GET` form, `POST` submission)
- **Access Level:** Public & Administrator (Public submissions are **`Pending` by default** with no choice of status; admins may optionally choose status).
- **Backend Function:** `write_register_pair(edition_year, category_id, ...)` in `src/services.py`
- **Description:** Enrolls a new pair into a championship edition (e.g. 2027) within an atomic transaction. Takes text input for carrier and carried competitors, automatically adds them into the `participant` table with their `approval_status`, and creates the competition entry.
- **Validations & Business Rules Enforced:**
  1. Validates that the selected edition offers the category (`has_category`).
  2. Inserts new competitor profiles into `participant` (or links existing records) within the atomic transaction, setting `approval_status` (`'Pending'` or `'Approved'`).
  3. Carrier and carried must be distinct participants (`carrier_id != carried_id`).
  4. Age verification: enforces that carrier is $\ge 40$ years old if registering for the "40+" category.
  5. Database triggers verify disjoint specialization (an entry cannot be both a pair and a team).
- **SQL Operations Executed Atomically:**
  ```sql
  -- Step 1: Add or resolve Carrier & Carried in participant table with approval status
  INSERT INTO participant (first_name, last_name, date_of_birth, weight_kg, country_code, approval_status)
  VALUES (%s, %s, %s, %s, %s, %s);
  
  -- Step 2: Insert core competition entry
  INSERT INTO competition_entry (edition_year, category_id, bib_number, registration_status)
  VALUES (%s, %s, %s, %s);
  
  -- Step 3: Insert subtype specialization
  INSERT INTO pair_entry (entry_id, carrier_id, carried_id)
  VALUES (%s, %s, %s);
  
  -- Step 4: Insert participation role records
  INSERT INTO participates_in (entry_id, participant_id, participant_role)
  VALUES (%s, %s, 'Carrier'), (%s, %s, 'Carried');
  
  -- Step 5: Record participant-edition history
  INSERT IGNORE INTO participates_in_edition (participant_id, edition_year)
  VALUES (%s, %s), (%s, %s);
  ```

#### **W2. Change Participant Country (Update Operation — `UPDATE`)**
- **URL / Route:** `/participants/update-country` (`GET` form, `POST` submission)
- **Access Level:** Administrator Only (Protected by `@admin_required` session decorator; non-admins are redirected to `/login`).
- **Backend Function:** `write_update_participant_country(participant_id, new_country_code)` in `src/services.py`
- **Description:** Updates the country affiliation of any participant in the database with immediate foreign key validation against the `country` table.
- **SQL Operations Executed Atomically:**
  ```sql
  -- Step 1: Verify target country exists
  SELECT country_name FROM country WHERE country_code = %s;
  
  -- Step 2: Perform parameterized update
  UPDATE participant 
  SET country_code = %s 
  WHERE participant_id = %s;
  ```

#### **W3. Delete Pending Entry (Delete Operation — `DELETE`) & Approval**
- **URL / Routes:** 
  - Manage entries view: `/entries/manage`
  - Delete entry action: `/entries/delete/<entry_id>` (`POST` action)
  - Approve entry action: `/entries/approve/<entry_id>` (`POST` action)
- **Access Level:** Administrator Only (Protected by `@admin_required` session decorator; non-admins are redirected to `/login`).
- **Backend Functions:** 
  - `write_delete_pending_entry(entry_id)` in `src/services.py`
  - `write_approve_pending_entry(entry_id)` in `src/services.py`
- **Description:** Allows administrators to approve or cancel pending applications while strictly guarding competition data integrity. When deleting a pending entry, the database cleans up related entries, removes edition participation, and automatically deletes orphaned participant records if they were created for that pending entry and have no other entries.
- **Safety Checks & Guardrails:**
  1. Status must be strictly `'Pending'`. Attempts to delete an `'Approved'` or `'Withdrawn'` entry are rejected with an error.
  2. Safety check: rejects deletion if race results already exist in `records_result`.
  3. Automatic cleanup: deletes orphaned competitors from `participant` and `participates_in_edition` when their sole pending entry is deleted, keeping the database consistent.
- **SQL Operations Executed Atomically for Deletion:**
  ```sql
  -- Step 1: Clean up dependent relationship and subtype rows
  DELETE FROM participates_in WHERE entry_id = %s;
  DELETE FROM pair_entry WHERE entry_id = %s;
  DELETE FROM team_entry WHERE entry_id = %s;
  DELETE FROM assigned_to WHERE entry_id = %s;
  DELETE FROM competition_entry WHERE entry_id = %s;

  -- Step 2: Remove edition participation if participant has no other entries in edition
  DELETE FROM participates_in_edition WHERE participant_id = %s AND edition_year = %s;

  -- Step 3: Remove orphaned participant if they have no other competition entries
  DELETE FROM participant_contact WHERE participant_id = %s;
  DELETE FROM participant WHERE participant_id = %s;
  ```
- **SQL Operations Executed Atomically for Approval:**
  ```sql
  -- Step 1: Confirm entry registration
  UPDATE competition_entry SET registration_status = 'Approved' WHERE entry_id = %s;

  -- Step 2: Update participant approval status
  UPDATE participant 
  SET approval_status = 'Approved'
  WHERE participant_id IN (
      SELECT participant_id FROM participates_in WHERE entry_id = %s
  );
  ```

## 6. Notes on queries

- **Safe Handling of Nullable Attributes:**
  - `LEFT JOIN` is strictly used when joining `official` with `records_result` because official IDs were not published on the website.
  - Names are joined using `CONCAT_WS(' ', first_name, last_name)` to gracefully handle contestants with no last name (e.g. single-word names such as Francois or Mathilde).
- **Application-Enforced Constraints:**
  - Constraints that MySQL cannot natively enforce via declarative table constraints (such as verifying carried person age/weight, preventing self-pairing `carrier_id != carried_id`, and enforcing carrier age $\ge 40$ in the 40+ category) are enforced programmatically inside atomic transactions in `src/services.py`.
- **Transaction Safety:**
  - Multi-table writes (such as pair registration and cascade-clean deletion of pending entries) use `src/db.py`'s `transaction()` context manager with `autocommit=False`. If any constraint or foreign key fails, the entire transaction is rolled back.
- **Participant Approval Lifecycle & Orphan Cleanup:**
  - When competitors register via `/register`, text inputs dynamically create new rows in the `participant` table with `approval_status` (`'Pending'` or `'Approved'`).
  - Administrators can approve pending entries via `/entries/approve/<id>`, atomically promoting both `competition_entry.registration_status` and `participant.approval_status` to `'Approved'`.
  - When an administrator deletes an approval-pending entry via `/entries/delete/<id>`, the database cleans up child records (`participates_in`, `pair_entry`), removes `participates_in_edition` associations for that year, and automatically deletes orphaned competitors from `participant` (and `participant_contact`) if they have no other competition entries. If a competitor has other entries, their `approval_status` is safely recalculated. This ensures zero orphaned records in the database.
