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
  - `src/services.py`: Data access service layer implementing the 5 read queries and 3 write operations.
  - `src/app.py`: Flask application routing, form handling, flash notifications, and template rendering.
  - `src/templates/`: Jinja2 templates (`base.html`, `index.html`, `entries.html`, `search.html`, `categories.html`, `results.html`, `register_pair.html`, `edit_participant.html`, `manage_entries.html`).
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

## 5. Features (in the order of the demonstration video)

| # | Feature | Page / URL | How to Trigger | What it does |
|---|---|---|---|---|
| **R1** | **Approved Entries per Edition** | `/entries` | Select edition (e.g. 2026) and optionally a category from the dropdown filters. | Parameterized `SELECT` filtering by `edition_year` and `registration_status = 'Approved'`. Joins `competition_entry`, `category`, `pair_entry`, `team_entry`, and `participant` with `CONCAT_WS` and `LEFT JOIN`s. |
| **R2** | **Participant Name Search** | `/search` | Enter a full or partial name (e.g. "Taisto", "Katja", "Joni") in the search input. | Performs case-insensitive wildcard matching using `CONCAT_WS(' ', first_name, last_name) LIKE %s`, displaying participant nationality, entered editions, categories, and roles. |
| **R3** | **Entries per Category Breakdown** | `/categories` | Navigate to `/categories` or filter by edition year. | Aggregate query (`GROUP BY hc.edition_year, c.category_id`) returning total, approved, and pending entry counts across categories for the chosen edition. |
| **R4** | **Heat Result Sheet with Time Differences** | `/results` | Select a race heat from the dropdown (e.g. 2026 Main Series: Race 6, Heat 1). | Displays heat rankings, bib numbers, raw times, penalties, final times (`raw_time + penalty_seconds`), and computes time differences (`time_diff`) relative to the heat winner using SQL window functions (`MIN(...) OVER ()`). Uses `LEFT JOIN` for nullable officials. |
| **R5** | **Average Final Time Analysis** | `/categories#averages` | Scroll down on the `/categories` analytics page or filter by edition. | Analytical query calculating `COUNT`, `AVG(raw_time + penalty_seconds)`, `MIN`, and `MAX` finish times per category for finished entrants. |
| **W1** | **Register a Pair (Create)** | `/register` | Choose edition (e.g. 2027), category, carrier, carried competitor, optional bib, and submit. | Multi-statement atomic transaction: verifies that the edition offers the category (`has_category`), verifies carried age/weight constraints, inserts `competition_entry`, `pair_entry`, `participates_in`, and updates `participates_in_edition`. |
| **W2** | **Change Participant Country (Update)** | `/participants/update-country` | Select participant and choose new country from the dropdown. | Executes parameterized `UPDATE participant SET country_code = %s WHERE participant_id = %s` inside a transaction after verifying country existence in `country`. |
| **W3** | **Delete Pending Entry (Delete)** | `/entries/manage` | Click "Delete Entry" on any entry with status 'Pending' (with confirmation prompt). | Atomic transaction: checks entry is strictly `Pending` (rejects deletion of `Approved` or raced entries), and removes associated `participates_in`, `pair_entry`, and `competition_entry` records. |

## 6. Notes on queries

- **Safe Handling of Nullable Attributes:**
  - `LEFT JOIN` is strictly used when joining `official` with `records_result` because official IDs were not published on the website.
  - Names are joined using `CONCAT_WS(' ', first_name, last_name)` to gracefully handle contestants with no last name (e.g. single-word names such as Francois or Mathilde).
- **Application-Enforced Constraints:**
  - Constraints that MySQL cannot natively enforce via declarative table constraints (such as verifying carried person age/weight, preventing self-pairing `carrier_id != carried_id`, and enforcing carrier age $\ge 40$ in the 40+ category) are enforced programmatically inside atomic transactions in `src/services.py`.
- **Transaction Safety:**
  - Multi-table writes (such as pair registration and cascade-clean deletion of pending entries) use `src/db.py`'s `transaction()` context manager with `autocommit=False`. If any constraint or foreign key fails, the entire transaction is rolled back.
