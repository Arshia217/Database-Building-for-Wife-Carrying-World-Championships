# Database-Building-for-Wife-Carrying-World-Championships
Part of project under the course Data and Applications.

# Wife Carrying World Championships (Eukonkanto): Database and Web App

**Team 20 (Team Tangled)** | Course: Data and Applications | Project Phase 4

Mini World: the Wife Carrying World Championships, Sonkajärvi, Finland (https://eukonkanto.fi).

## 1. Paradigm and stack

- **Paradigm:** relational. **DBMS:** MySQL 8.0.46 (Community Server).
- **Backend:** Python with Flask and PyMySQL (raw, parameterised SQL only; no ORM). *(to be filled in when the app is finished)*
- **Frontend:** server-rendered Jinja templates (HTML/CSS). *(to be filled in)*
- **Status of this README:** schema and data are done; the application sections below are marked *(to be completed)*.

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

- **2026:** full results, 87 entries including 2024/2025 winners, 86 results in 8 heats (Friday sprint: 3 heats + final; Saturday: Team, Women, 40+, Main Series).
- **2024 and 2025:** gold medalists only (the site gives no heat-level results for earlier years).
- **2027:** scheduled edition (2-3 July 2027) with the Main Series, Sprint and Team Series categories, so new registrations can be made.
- Not loaded because the site does not publish them: officials, dates of birth, weights, contact numbers.

**Interpretations (not data errors):**
- When the website lists two countries for one pair or team, they were matched to the names in order.
- The 15 s penalty of *Team 2 SPOLK* is treated as included in the listed time (`raw_time = listed time - 15`).
- Names shown with one word only (Francois, Mathilde, Svetlana, Vaimo, Sanna) have no last name.
- The sprint is modelled as race 1 (heats 1-3) and race 2 (final). Saturday series are races 3-6 with one heat each.
- Category `minimum_age` (17) applies to the carried person; the 40+ rule "carrier must be 40 or older" is in the rules text and is checked by the application.
- Only 2026 has heat-level data, so cross-edition time comparisons only cover 2026.

## 4. Setup and run

```
mysql -u <user> -p < src/schema.sql      # drops and recreates database eukakanto
mysql -u <user> -p < src/populate.sql    # loads the data
pip install -r src/requirements.txt      # (to be completed)
python src/app.py                        # then open http://localhost:5000   (to be completed)
```

Database credentials are read from environment variables (`DB_HOST`, `DB_USER`, `DB_PASS`, `DB_NAME`); no password is stored in the code.

## 5. Features *(to be completed, in the order of the video)*

Planned: 5 read queries (approved entries per edition, name search, entries per category, heat result sheet with time difference, average final time) and 3 writes (register a pair: create; change a participant's country: update; delete a pending entry: delete). Each will be listed here with its page, how to trigger it, and what it does.

## 6. Notes on queries

Because some columns are NULL, queries use `LEFT JOIN` for officials, `CONCAT_WS` for full names, and do not rely on age, since no date of birth is stored. Rules that the database cannot enforce (carried person's age/weight, exactly 3 carriers and 1 carried per team, every entry having exactly one subtype row) are enforced in the application inside one transaction.

